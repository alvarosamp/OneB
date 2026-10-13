#property strict
#property version "1.00"
#property description "Tester-only recorder. Never sends orders. Uses original indicator defaults."

enum VendorFamily { GOLD_FAKEOUT, LONDON_BOX, DMI_13X, PIPS_100, DUCK_V4, NASDAQ_GAP, CAIXA_AMERICANA, NATIVE_EMA_CONTROL };
input VendorFamily Family=GOLD_FAKEOUT;
input int BufferCount=12;
input int ClosedBarLookback=12;
input int MaxObjects=1000;
input string RunLabel="audit_v1";
input bool CalculateEveryTick=true;
input bool OverrideGapSession=false;
input int GapOpenHour=16;
input int GapOpenMinute=30;
int handle=INVALID_HANDLE, buffersFile=INVALID_HANDLE, objectsFile=INVALID_HANDLE;
datetime lastBar=0;

int LoadOriginal()
{
   switch(Family)
   {
      case GOLD_FAKEOUT: return iCustom(_Symbol,_Period,"Purchased\\GOLD Fakeout CRAZY v4");
      case LONDON_BOX: return iCustom(_Symbol,_Period,"Purchased\\Estratégia Caixa de Londres");
      case DMI_13X: return iCustom(_Symbol,_Period,"Purchased\\Estratégia 13X - EMA13 + DMI");
      case PIPS_100: return iCustom(_Symbol,_Period,"Purchased\\Estratégia 100 PIPS POR DIA");
      case DUCK_V4: return iCustom(_Symbol,_Period,"Purchased\\DuckV4");
      case NASDAQ_GAP:
         return iCustom(_Symbol,_Period,"Purchased\\Estratégia NASDAQ GAP DRIVE v6");
      case CAIXA_AMERICANA: return iCustom(_Symbol,_Period,"Purchased\\Caixa Americana V2");
      case NATIVE_EMA_CONTROL: return iMA(_Symbol,_Period,13,0,MODE_EMA,PRICE_CLOSE);
   }
   return INVALID_HANDLE;
}

int OnInit()
{
   Print("AUDIT INIT: family=",(int)Family,"; visual=",MQLInfoInteger(MQL_VISUAL_MODE),"; buffers=",BufferCount);
   if(!MQLInfoInteger(MQL_TESTER)) { Print("BLOCKED: tester only, no live execution."); return INIT_FAILED; }
   if(BufferCount<1 || BufferCount>64 || ClosedBarLookback<2 || ClosedBarLookback>500 || MaxObjects<1)
      return INIT_PARAMETERS_INCORRECT;
   if(GapOpenHour<0 || GapOpenHour>23 || GapOpenMinute<0 || GapOpenMinute>59)
      return INIT_PARAMETERS_INCORRECT;
   // Explicit parameter loading returned error 4002 despite exported defaults.
   // Do not silently ignore a requested override or claim this scenario ran.
   if(OverrideGapSession) { Print("BLOCKED: Gap session parameter signature not certified; defaults only."); return INIT_PARAMETERS_INCORRECT; }
   Print("AUDIT MODE: every_tick=",CalculateEveryTick,"; gap_session_override=",OverrideGapSession,
      "; gap_hour=",GapOpenHour,"; gap_minute=",GapOpenMinute);
   if(StringFind(RunLabel,"\\")>=0 || StringFind(RunLabel,"/")>=0 || StringFind(RunLabel,"..")>=0)
      return INIT_PARAMETERS_INCORRECT;
   handle=LoadOriginal();
   Print("AUDIT LOAD: handle=",handle,"; error=",GetLastError());
   if(handle==INVALID_HANDLE) { Print("Original load failed: ",GetLastError()); return INIT_FAILED; }
   // Visual mode is needed to audit object-only signals as drawn by the vendor.
   if(MQLInfoInteger(MQL_VISUAL_MODE) && !ChartIndicatorAdd(0,0,handle))
      { Print("Chart attach failed: ",GetLastError()); return INIT_FAILED; }
   string prefix=RunLabel+"_"+IntegerToString((int)Family)+"_"+_Symbol+"_"+EnumToString(_Period);
   // FILE_COMMON intentionally omitted: outputs stay inside the isolated tester agent.
   buffersFile=FileOpen(prefix+"_buffers.csv",FILE_WRITE|FILE_CSV|FILE_ANSI,';',CP_UTF8);
   objectsFile=FileOpen(prefix+"_objects.csv",FILE_WRITE|FILE_CSV|FILE_ANSI,';',CP_UTF8);
   if(buffersFile==INVALID_HANDLE || objectsFile==INVALID_HANDLE) return INIT_FAILED;
   FileWrite(buffersFile,"observed_at","bar_time","shift","buffer","status","value","error");
   FileWrite(objectsFile,"observed_at","name","type","time0","price0","time1","price1","text");
   FileFlush(buffersFile); FileFlush(objectsFile);
   Print("AUDIT START: ",prefix,"; original defaults; timestamps are broker raw; NO ORDERS.");
   return INIT_SUCCEEDED;
}

void Snapshot()
{
   datetime observed=TimeCurrent();
   int available=BarsCalculated(handle);
   for(int b=0;b<BufferCount;b++)
      for(int shift=1;shift<=ClosedBarLookback;shift++)
      {
         datetime bar=iTime(_Symbol,_Period,shift);
         if(bar==0) continue;
         double value[1];
         ResetLastError();
         int copied=CopyBuffer(handle,b,shift,1,value);
         int error=GetLastError();
         string status=(available<=0 || copied!=1) ? "unavailable" :
            (value[0]==EMPTY_VALUE || !MathIsValidNumber(value[0]) ? "empty" : "ok");
         FileWrite(buffersFile,TimeToString(observed,TIME_DATE|TIME_SECONDS),
            TimeToString(bar,TIME_DATE|TIME_SECONDS),shift,b,status,
            status=="ok" ? DoubleToString(value[0],12) : "",error);
      }
   // Object APIs may also expose the vendor's drawing state on the tester's
   // hidden chart. Capture it, but an empty hidden chart is NOT proof of no signal.
   {
      if(MQLInfoInteger(MQL_VISUAL_MODE)) ChartRedraw();
      int count=ObjectsTotal(0,-1,-1);
      FileWrite(objectsFile,TimeToString(observed,TIME_DATE|TIME_SECONDS),"__snapshot__",count,"",0,"",0,
         count>MaxObjects ? "TRUNCATED" : "complete");
      for(int n=0;n<MathMin(count,MaxObjects);n++)
      {
         string name=ObjectName(0,n,-1,-1);
         FileWrite(objectsFile,TimeToString(observed,TIME_DATE|TIME_SECONDS),name,
            ObjectGetInteger(0,name,OBJPROP_TYPE),
            TimeToString((datetime)ObjectGetInteger(0,name,OBJPROP_TIME,0),TIME_DATE|TIME_SECONDS),
            ObjectGetDouble(0,name,OBJPROP_PRICE,0),
            TimeToString((datetime)ObjectGetInteger(0,name,OBJPROP_TIME,1),TIME_DATE|TIME_SECONDS),
            ObjectGetDouble(0,name,OBJPROP_PRICE,1),ObjectGetString(0,name,OBJPROP_TEXT));
      }
   }
   FileFlush(buffersFile); FileFlush(objectsFile);
}

void OnTick()
{
   // Hidden tester indicators can be lazy-calculated. Match visual calculation
   // frequency without changing the closed-bar sampling frequency or sending orders.
   if(CalculateEveryTick) { double everyTick[1]; CopyBuffer(handle,0,0,1,everyTick); }
   datetime current=iTime(_Symbol,_Period,0);
   if(current==0 || current==lastBar) return;
   if(lastBar==0) Print("AUDIT FIRST TICK: ",TimeToString(TimeCurrent(),TIME_DATE|TIME_SECONDS));
   // Record readiness failures once per bar too. Retrying every tick hides the
   // unavailable window and can generate millions of diagnostic log lines.
   lastBar=current;
   // Force original calculation before sampling completed bars; no bar-zero decision.
   double sync[1]; CopyBuffer(handle,0,0,1,sync);
   Snapshot();
}

void OnDeinit(const int reason)
{
   if(buffersFile!=INVALID_HANDLE) FileClose(buffersFile);
   if(objectsFile!=INVALID_HANDLE) FileClose(objectsFile);
   if(handle!=INVALID_HANDLE) IndicatorRelease(handle);
   Print("AUDIT END reason=",reason,"; no order functions in this recorder.");
}
