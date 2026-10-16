//+------------------------------------------------------------------+
//| OneB Risco — risco medido no gráfico (não é sinal de compra/venda)|
//| Mostra: quanto o mercado deve mexer hoje (previsão aprovada em   |
//| teste), stop de 1,5 ATR de 1 h e a chance real de cada alvo, lote |
//| para o seu saldo e risco, qualidade do horário e CPI/payroll/FOMC.|
//| Não envia ordens.                                                 |
//+------------------------------------------------------------------+
#property copyright "OneB"
#property version   "1.00"
#property description "Risco medido, não sinal: amplitude prevista, stop por ATR, chance real dos alvos, lote e horário."
#property indicator_chart_window
#property indicator_plots 0

input double InpBalance = 0.0;      // Saldo (0 = saldo da conta)
input double InpRiskPct = 1.0;      // Risco por operação (%)
input double InpStopATR = 1.5;      // Stop em ATR de 1 hora
input bool   InpLines   = true;     // Desenhar linhas de "até onde o dia costuma ir"
input color  InpColor   = clrSilver;// Cor do texto
input int    InpFontSize = 9;       // Tamanho da letra

//@@DATA@@

#define PREFIX "OneB_"
string ASSET_LABEL[4] = {"Nasdaq 100", "S&P 500", "Ouro", "Euro/dólar"};
string HOUR_TEXT[5] = {"boa", "pico (mais movimento: reduza o lote)", "parada (o custo pesa mais)", "evitar (spread alto)", "fechada"};
int g_asset = -1;
int g_atr = INVALID_HANDLE;

int AssetIndex(string sym)
  {
   string s = sym;
   StringToUpper(s);
   if(StringFind(s, "XAU") >= 0 || StringFind(s, "GOLD") >= 0) return 2;
   if(StringFind(s, "EURUSD") >= 0) return 3;
   if(StringFind(s, "US500") >= 0 || StringFind(s, "SPX") >= 0 || StringFind(s, "SP500") >= 0) return 1;
   if(StringFind(s, "US100") >= 0 || StringFind(s, "NAS") >= 0 || StringFind(s, "USTEC") >= 0 || StringFind(s, "NDX") >= 0) return 0;
   return -1;
  }

// segundo domingo de março / primeiro de novembro (horário de verão dos EUA)
datetime NthSunday(int year, int month, int n)
  {
   MqlDateTime t; ZeroMemory(t);
   t.year = year; t.mon = month; t.day = 1;
   int found = 0;
   for(int d = 1; d <= 14; d++)
     {
      t.day = d;
      datetime x = StructToTime(t);
      MqlDateTime c; TimeToStruct(x, c);
      if(c.day_of_week == 0 && ++found == n) return x;
     }
   return 0;
  }

int NYOffsetHours(datetime gmt)
  {
   MqlDateTime t; TimeToStruct(gmt, t);
   datetime start = NthSunday(t.year, 3, 2) + 7 * 3600;  // 02:00 EST = 07:00 UTC
   datetime end   = NthSunday(t.year, 11, 1) + 6 * 3600; // 02:00 EDT = 06:00 UTC
   return (gmt >= start && gmt < end) ? -4 : -5;
  }

string Num(double v, int digits)
  {
   string s = DoubleToString(v, digits);
   StringReplace(s, ".", ",");
   return s;
  }

void Label(int row, string text, color clr)
  {
   string name = PREFIX + "L" + IntegerToString(row);
   if(ObjectFind(0, name) < 0)
     {
      ObjectCreate(0, name, OBJ_LABEL, 0, 0, 0);
      ObjectSetInteger(0, name, OBJPROP_CORNER, CORNER_LEFT_UPPER);
      ObjectSetInteger(0, name, OBJPROP_XDISTANCE, 10);
      ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
      ObjectSetString(0, name, OBJPROP_FONT, "Segoe UI");
     }
   ObjectSetInteger(0, name, OBJPROP_YDISTANCE, 22 + row * (InpFontSize + 7));
   ObjectSetInteger(0, name, OBJPROP_FONTSIZE, InpFontSize);
   ObjectSetInteger(0, name, OBJPROP_COLOR, clr);
   ObjectSetString(0, name, OBJPROP_TEXT, text);
  }

void HLine(string id, double price, string tip)
  {
   string name = PREFIX + id;
   if(ObjectFind(0, name) < 0)
     {
      ObjectCreate(0, name, OBJ_HLINE, 0, 0, price);
      ObjectSetInteger(0, name, OBJPROP_STYLE, STYLE_DOT);
      ObjectSetInteger(0, name, OBJPROP_COLOR, clrDodgerBlue);
      ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
      ObjectSetInteger(0, name, OBJPROP_BACK, true);
     }
   ObjectSetDouble(0, name, OBJPROP_PRICE, price);
   ObjectSetString(0, name, OBJPROP_TOOLTIP, tip);
  }

// CPI, payroll e FOMC (EUA) entre `from` e `to` (GMT). Preenche `text` com o próximo e diz se algum cai no pregão atual.
bool UsEvents(datetime from, datetime to, datetime sessFrom, datetime sessTo, string &text)
  {
   text = "";
   MqlCalendarValue values[];
   long shift = (long)(TimeTradeServer() - TimeGMT()); // calendário vem no horário do servidor
   bool inSession = false;
   if(CalendarValueHistory(values, (datetime)(from + shift), (datetime)(to + shift), "US") <= 0) return false;
   for(int i = 0; i < ArraySize(values); i++)
     {
      MqlCalendarEvent ev;
      if(!CalendarEventById(values[i].event_id, ev)) continue;
      if(ev.importance != CALENDAR_IMPORTANCE_HIGH) continue;
      string n = ev.name;
      bool key = StringFind(n, "CPI") >= 0 || StringFind(n, "Nonfarm") >= 0 || StringFind(n, "Fed Interest Rate") >= 0 || StringFind(n, "FOMC") >= 0;
      if(!key) continue;
      datetime gmt = (datetime)(values[i].time - shift);
      if(gmt >= sessFrom && gmt < sessTo) inSession = true;
      if(gmt >= TimeGMT() && text == "")
        {
         MqlDateTime b; TimeToStruct(gmt - 3 * 3600, b); // Brasília (UTC-3)
         text = StringFormat("%s em %02d/%02d às %02d:%02d (Brasília): o movimento costuma multiplicar na 1ª meia hora. Reduza o lote ou espere.",
                             n, b.day, b.mon, b.hour, b.min);
        }
     }
   return inSession;
  }

// horário do servidor da corretora para um instante GMT (assume que o servidor segue o horário de verão de NY,
// como a HonorPro, cuja vela diária vira às 17:00 de NY)
datetime ServerOf(datetime gmt)
  {
   long shiftNow = (long)(TimeTradeServer() - TimeGMT());
   return (datetime)(gmt + shiftNow + (NYOffsetHours(gmt) - NYOffsetHours(TimeGMT())) * 3600);
  }

int FirstAtOrAfter(const MqlRates &r[], int n, datetime t)
  {
   int lo = 0, hi = n;
   while(lo < hi)
     {
      int mid = (lo + hi) / 2;
      if(r[mid].time < t) lo = mid + 1; else hi = mid;
     }
   return lo;
  }

// máxima - mínima entre dois instantes GMT; `op` = abertura da primeira barra
bool RangeOf(const MqlRates &r[], int n, datetime g0, datetime g1, double &rng, double &op, int &bars)
  {
   datetime s0 = ServerOf(g0), s1 = ServerOf(g1);
   int i = FirstAtOrAfter(r, n, s0);
   double hi = -DBL_MAX, lo = DBL_MAX;
   bars = 0;
   op = (i < n) ? r[i].open : 0;
   for(; i < n && r[i].time < s1; i++)
     {
      hi = MathMax(hi, r[i].high);
      lo = MathMin(lo, r[i].low);
      bars++;
     }
   rng = bars > 0 ? hi - lo : 0;
   return bars > 0;
  }

// janela do sessfc_v1 para o dia `day0` (meia-noite GMT da data de NY): madrugada desde 18:00 de NY da véspera,
// entrada às 13:30 GMT (10:30 de Brasília), fechamento às 16:00 de NY
void WindowBounds(datetime day0, datetime &pre, datetime &entry, datetime &close)
  {
   entry = day0 + 13 * 3600 + 30 * 60;
   close = day0 + 16 * 3600 - NYOffsetHours(entry) * 3600;
   datetime prev = day0 - 86400;
   pre = prev + 18 * 3600 - NYOffsetHours(prev + 22 * 3600) * 3600;
  }

int SessionForecast(int a, MqlDateTime &nt, bool eventToday, int row, int digits)
  {
   if(!SESS_ON[a]) return row;
   MqlRates r[];
   int n = CopyRates(_Symbol, PERIOD_M5, 0, 16000, r);
   if(n < 2000) return row;
   MqlDateTime d0 = nt; d0.hour = 0; d0.min = 0; d0.sec = 0;
   datetime today = StructToTime(d0); // data de NY à meia-noite (lida como GMT)
   datetime gmt = TimeGMT();
   double lr[];
   ArrayResize(lr, 0);
   for(int k = 1; k <= 60 && ArraySize(lr) < 22; k++)
     {
      datetime day0 = today - k * 86400;
      MqlDateTime w; TimeToStruct(day0, w);
      if(w.day_of_week == 0 || w.day_of_week == 6) continue;
      datetime pre, entry, close;
      WindowBounds(day0, pre, entry, close);
      double rng, op; int bars;
      if(RangeOf(r, n, entry, close, rng, op, bars) && bars >= 24 && op > 0 && rng > 0)
        {
         int sz = ArraySize(lr);
         ArrayResize(lr, sz + 1);
         lr[sz] = MathLog(rng / op); // mais recente primeiro
        }
     }
   if(ArraySize(lr) < 22) return row;
   datetime pre, entry, close;
   WindowBounds(today, pre, entry, close);
   if(gmt < entry)
     {
      Label(row++, "Das 10:30 ao fechamento de NY: a previsão sai às 10:30 de Brasília.", InpColor);
      return row;
     }
   double preRng, entryOp, soFar, op2; int b1, b2;
   if(!RangeOf(r, n, pre, entry, preRng, op2, b1) || !RangeOf(r, n, entry, close, soFar, entryOp, b2) || entryOp <= 0 || preRng <= 0)
      return row;
   double w5 = 0, m22 = 0;
   for(int i = 0; i < 22; i++) { m22 += lr[i]; if(i < 5) w5 += lr[i]; }
   double mid = SESS_COEF[a][0] + SESS_COEF[a][1] * lr[0] + SESS_COEF[a][2] * w5 / 5.0 + SESS_COEF[a][3] * m22 / 22.0
                + SESS_COEF[a][4] * MathLog(preRng / entryOp) + SESS_COEF[a][5] * (eventToday ? 1.0 : 0.0);
   double expP = MathExp(mid) * entryOp, lowP = MathExp(mid + SESS_Q10[a]) * entryOp, highP = MathExp(mid + SESS_Q90[a]) * entryOp;
   int dd = digits > 2 ? 4 : 1;
   Label(row++, StringFormat("Das 10:30 ao fechamento de NY: deve andar ~%s; em 8 de 10 dias, de %s a %s. %s: %s.",
                             Num(expP, dd), Num(lowP, dd), Num(highP, dd), gmt >= close ? "Janela encerrada, andou" : "Até agora", Num(soFar, dd)),
         soFar > highP ? clrOrange : InpColor);
   return row;
  }

void Draw()
  {
   if(g_asset < 0)
     {
      Label(0, "OneB: ativo sem estudo (use Nasdaq US100, S&P US500, ouro XAUUSD ou EURUSD).", InpColor);
      return;
     }
   int a = g_asset;
   int digits = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
   double point = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   double price = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   int row = 0;
   Label(row++, "OneB · " + ASSET_LABEL[a] + " · risco medido, não é sinal de compra ou venda", clrDodgerBlue);

   // pregão atual (vela diária da corretora; HonorPro vira às 17:00 de NY)
   datetime gmt = TimeGMT();
   int ny = NYOffsetHours(gmt);
   MqlDateTime nt; TimeToStruct(gmt + ny * 3600, nt);
   MqlDateTime sd = nt; sd.hour = 17; sd.min = 0; sd.sec = 0;
   datetime sessEndNy = StructToTime(sd);
   if(nt.hour >= 17) sessEndNy += 86400;
   datetime sessTo = sessEndNy - ny * 3600;
   datetime sessFrom = sessTo - 23 * 3600; // abre 18:00 de NY da véspera
   string evText;
   bool eventToday = UsEvents(gmt - 3600, gmt + 7 * 86400, sessFrom, sessTo, evText);

   MqlRates d1[];
   ArraySetAsSeries(d1, true);
   int got = CopyRates(_Symbol, PERIOD_D1, 0, 25, d1);
   if(got >= 24)
     {
      double lr[22];
      double sum5 = 0, sum22 = 0;
      for(int i = 0; i < 22; i++)
        {
         double rng = (d1[i + 1].high - d1[i + 1].low) / d1[i + 2].close; // pregões FECHADOS (1 = ontem)
         lr[i] = MathLog(MathMax(rng, 1e-6));
         sum22 += lr[i];
         if(i < 5) sum5 += lr[i];
        }
      double mid = COEF[a][0] + COEF[a][1] * lr[0] + COEF[a][2] * sum5 / 5.0 + COEF[a][3] * sum22 / 22.0 + COEF[a][4] * (eventToday ? 1.0 : 0.0);
      double expPct = MathExp(mid) * 100, lowPct = MathExp(mid + Q10[a]) * 100, highPct = MathExp(mid + Q90[a]) * 100;
      double ref = d1[1].close;
      double expPts = expPct / 100 * ref;
      double soFar = d1[0].high - d1[0].low;
      Label(row++, StringFormat("Hoje deve mexer ~%s (%s%%) entre máxima e mínima; em 8 de 10 dias, de %s a %s.%s",
                                Num(expPts, digits > 2 ? 4 : 1), Num(expPct, 2), Num(lowPct / 100 * ref, digits > 2 ? 4 : 1),
                                Num(highPct / 100 * ref, digits > 2 ? 4 : 1), eventToday ? " Dia de evento: já incluído." : ""), InpColor);
      Label(row++, StringFormat("Até agora andou %s (%s%% do previsto). Diz QUANTO, não para onde.", Num(soFar, digits > 2 ? 4 : 1),
                                Num(expPts > 0 ? soFar / expPts * 100 : 0, 0)), InpColor);
      if(InpLines)
        {
         HLine("reach_high", d1[0].low + expPts, "OneB: máxima se o dia andar o previsto a partir da mínima de hoje");
         HLine("reach_low", d1[0].high - expPts, "OneB: mínima se o dia andar o previsto a partir da máxima de hoje");
        }
     }
   else
      Label(row++, "Sem histórico diário suficiente para a previsão.", InpColor);
   row = SessionForecast(a, nt, eventToday, row, digits);

   double atr[1];
   if(CopyBuffer(g_atr, 0, 1, 1, atr) == 1 && atr[0] > 0)
     {
      double stop = InpStopATR * atr[0];
      double spread = (double)SymbolInfoInteger(_Symbol, SYMBOL_SPREAD) * point;
      Label(row++, StringFormat("Stop de %s ATR de 1 h: %s · alvos 1R %s · 2R %s · 3R %s · spread agora %s (%s%% do stop)",
                                Num(InpStopATR, 1), Num(stop, digits), Num(stop, digits), Num(2 * stop, digits), Num(3 * stop, digits),
                                Num(spread, digits), Num(stop > 0 ? spread / stop * 100 : 0, 1)), InpColor);
      if(MathAbs(InpStopATR - 1.5) < 1e-9)
         Label(row++, StringFormat("Chance real do alvo antes do stop (2023-2026, com spread): compra %s%% / %s%% / %s%% · venda %s%% / %s%% / %s%%",
                                   Num(PTARGET[a][0] * 100, 0), Num(PTARGET[a][1] * 100, 0), Num(PTARGET[a][2] * 100, 0),
                                   Num(PTARGET[a][3] * 100, 0), Num(PTARGET[a][4] * 100, 0), Num(PTARGET[a][5] * 100, 0)), InpColor);
      else
         Label(row++, "Chance medida dos alvos só existe para stop de 1,5 ATR.", InpColor);

      double balance = InpBalance > 0 ? InpBalance : AccountInfoDouble(ACCOUNT_BALANCE);
      double tickValue = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE_LOSS);
      double tickSize = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
      double vmin = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN), vstep = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
      if(tickValue > 0 && tickSize > 0 && vstep > 0)
        {
         double perLot = stop / tickSize * tickValue;
         double riskMoney = balance * InpRiskPct / 100.0;
         double lots = MathFloor(riskMoney / perLot / vstep + 1e-9) * vstep;
         if(lots < vmin)
            Label(row++, StringFormat("Lote: nem o mínimo (%s) cabe em %s%% de %s: arriscaria %s. Não opere este ativo com esse saldo.",
                                      Num(vmin, 2), Num(InpRiskPct, 1), Num(balance, 2), Num(vmin * perLot, 2)), clrOrangeRed);
         else
            Label(row++, StringFormat("Lote para arriscar %s%% de %s: %s (risco real %s).", Num(InpRiskPct, 1), Num(balance, 2),
                                      Num(lots, 2), Num(lots * perLot, 2)), InpColor);
        }
     }

   int nyHour = nt.hour;
   int cls = HOURCLASS[a][nyHour];
   MqlDateTime br; TimeToStruct(gmt - 3 * 3600, br);
   Label(row++, StringFormat("Hora atual (%02dh de Brasília): %s.", br.hour, HOUR_TEXT[cls]), cls >= 2 ? clrOrange : InpColor);
   if(evText != "") Label(row++, evText, clrOrange);
   Label(row++, "Nenhuma regra de direção passou nos testes do OneB: a decisão é sua.", clrGray);
   for(int r = row; r < row + 4; r++) ObjectDelete(0, PREFIX + "L" + IntegerToString(r));
   ChartRedraw();
  }

int OnInit()
  {
   g_asset = AssetIndex(_Symbol);
   g_atr = iATR(_Symbol, PERIOD_H1, 14);
   if(g_atr == INVALID_HANDLE) return INIT_FAILED;
   EventSetTimer(30);
   Draw();
   return INIT_SUCCEEDED;
  }

void OnDeinit(const int reason)
  {
   EventKillTimer();
   ObjectsDeleteAll(0, PREFIX);
   if(g_atr != INVALID_HANDLE) IndicatorRelease(g_atr);
  }

void OnTimer() { Draw(); }

int OnCalculate(const int rates_total, const int prev_calculated, const datetime &time[], const double &open[], const double &high[],
                const double &low[], const double &close[], const long &tick_volume[], const long &volume[], const int &spread[])
  {
   if(prev_calculated == 0) Draw();
   return rates_total;
  }
