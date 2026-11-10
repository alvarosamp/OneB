#property script_show_inputs
#property strict

input datetime StartDate = D'2021.01.01 00:00';
input datetime EndDate   = D'2030.01.01 00:00';
input ENUM_TIMEFRAMES Timeframe = PERIOD_M1;
input int ChunkDays = 30;

bool IsResearchSymbol(const string name,const string description)
{
   string text=name+" "+description;
   StringToUpper(text);
   string terms[]={"XAU","GOLD","NAS","US100","USTEC","NQ","GC"};
   for(int i=0;i<ArraySize(terms);i++)
      if(StringFind(text,terms[i])>=0)
         return true;
   return false;
}

string SafeName(string value)
{
   string invalid[]={"\\","/",":","*","?","\"","<",">","|"," ","."};
   for(int i=0;i<ArraySize(invalid);i++)
      StringReplace(value,invalid[i],"_");
   return value;
}

void WriteSpecification(const string symbol)
{
   string file="CodexMarketData\\"+SafeName(symbol)+"_spec.csv";
   int h=FileOpen(file,FILE_WRITE|FILE_CSV|FILE_ANSI|FILE_COMMON,',');
   if(h==INVALID_HANDLE) { Print("Spec FileOpen failed: ",symbol," error=",GetLastError()); return; }
   FileWrite(h,"field","value");
   FileWrite(h,"symbol",symbol);
   FileWrite(h,"description",SymbolInfoString(symbol,SYMBOL_DESCRIPTION));
   FileWrite(h,"path",SymbolInfoString(symbol,SYMBOL_PATH));
   FileWrite(h,"currency_base",SymbolInfoString(symbol,SYMBOL_CURRENCY_BASE));
   FileWrite(h,"currency_profit",SymbolInfoString(symbol,SYMBOL_CURRENCY_PROFIT));
   FileWrite(h,"digits",(string)SymbolInfoInteger(symbol,SYMBOL_DIGITS));
   FileWrite(h,"point",DoubleToString(SymbolInfoDouble(symbol,SYMBOL_POINT),12));
   FileWrite(h,"tick_size",DoubleToString(SymbolInfoDouble(symbol,SYMBOL_TRADE_TICK_SIZE),12));
   FileWrite(h,"tick_value",DoubleToString(SymbolInfoDouble(symbol,SYMBOL_TRADE_TICK_VALUE),8));
   FileWrite(h,"contract_size",DoubleToString(SymbolInfoDouble(symbol,SYMBOL_TRADE_CONTRACT_SIZE),8));
   FileWrite(h,"volume_min",DoubleToString(SymbolInfoDouble(symbol,SYMBOL_VOLUME_MIN),8));
   FileWrite(h,"volume_step",DoubleToString(SymbolInfoDouble(symbol,SYMBOL_VOLUME_STEP),8));
   FileWrite(h,"server_now",TimeToString(TimeTradeServer(),TIME_DATE|TIME_SECONDS));
   FileWrite(h,"gmt_now",TimeToString(TimeGMT(),TIME_DATE|TIME_SECONDS));
   FileClose(h);
}

long ExportSymbol(const string symbol)
{
   if(!SymbolSelect(symbol,true)) { Print("SymbolSelect failed: ",symbol); return 0; }
   string tf=EnumToString(Timeframe);
   string file="CodexMarketData\\"+SafeName(symbol)+"_"+tf+".csv";
   int h=FileOpen(file,FILE_WRITE|FILE_CSV|FILE_ANSI|FILE_COMMON,',');
   if(h==INVALID_HANDLE) { Print("Rates FileOpen failed: ",symbol," error=",GetLastError()); return 0; }
   FileWrite(h,"time_epoch","server_time","open","high","low","close","tick_volume","spread_points","real_volume");
   datetime cursor=StartDate;
   datetime finish=MathMin(EndDate,TimeTradeServer()+1);
   long total=0;
   while(cursor<finish && !IsStopped())
   {
      datetime next=MathMin(cursor+(datetime)(86400*MathMax(1,ChunkDays)),finish);
      MqlRates rates[];
      ArraySetAsSeries(rates,false);
      int copied=CopyRates(symbol,Timeframe,cursor,next,rates);
      if(copied>0)
      {
         for(int i=0;i<copied;i++)
         {
            if(i==copied-1 && next<finish) continue; // evita duplicata na fronteira
            FileWrite(h,(long)rates[i].time,TimeToString(rates[i].time,TIME_DATE|TIME_MINUTES),
                      DoubleToString(rates[i].open,(int)SymbolInfoInteger(symbol,SYMBOL_DIGITS)),
                      DoubleToString(rates[i].high,(int)SymbolInfoInteger(symbol,SYMBOL_DIGITS)),
                      DoubleToString(rates[i].low,(int)SymbolInfoInteger(symbol,SYMBOL_DIGITS)),
                      DoubleToString(rates[i].close,(int)SymbolInfoInteger(symbol,SYMBOL_DIGITS)),
                      rates[i].tick_volume,rates[i].spread,rates[i].real_volume);
            total++;
         }
      }
      cursor=next;
   }
   FileClose(h);
   WriteSpecification(symbol);
   Print("EXPORTED ",symbol," rows=",total," file=Common\\Files\\",file);
   return total;
}

void OnStart()
{
   Print("Codex read-only broker history export started. No trading functions are used.");
   int count=SymbolsTotal(false);
   int matched=0;
   long rows=0;
   for(int i=0;i<count && !IsStopped();i++)
   {
      string symbol=SymbolName(i,false);
      if(!IsResearchSymbol(symbol,SymbolInfoString(symbol,SYMBOL_DESCRIPTION))) continue;
      matched++;
      rows+=ExportSymbol(symbol);
   }
   Print("EXPORT COMPLETE matched_symbols=",matched," total_rows=",rows,
         " common_path=",TerminalInfoString(TERMINAL_COMMONDATA_PATH),"\\Files\\CodexMarketData");
}
