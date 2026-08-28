//+------------------------------------------------------------------+
//| MTF Liquidity Structure - visual decision-support indicator     |
//| Intended chart: M1. Works with broker symbols for XAUUSD/NAS100 |
//+------------------------------------------------------------------+
#property copyright "OneB Market"
#property version   "1.00"
#property indicator_chart_window
#property indicator_buffers 2
#property indicator_plots   2
#property indicator_type1   DRAW_ARROW
#property indicator_type2   DRAW_ARROW
#property indicator_color1  clrLime
#property indicator_color2  clrTomato
#property indicator_width1  2
#property indicator_width2  2
#property indicator_label1  "Long attack"
#property indicator_label2  "Short attack"

input int    InpSwingStrength       = 3;     // Candles on each side of a swing
input int    InpH4EMAPeriod          = 50;    // H4 directional fallback
input int    InpSetupExpiryH1Bars    = 12;    // BOS is valid for this many H1 bars
input int    InpM15LiquidityLookback = 20;    // M15 liquidity range
input int    InpM5BreakLookback      = 5;     // M5 confirmation range
input int    InpM1BreakLookback      = 5;     // M1 attack range
input int    InpArrowOffsetPoints    = 80;    // Visual offset only

double BuyBuffer[];
double SellBuffer[];
int H4EmaHandle = INVALID_HANDLE;

// Returns true only after the swing has been confirmed by bars to its right.
bool IsSwingHigh(const string symbol, ENUM_TIMEFRAMES tf, int shift, int strength)
{
   if(shift < strength + 1) return false;
   double candidate = iHigh(symbol, tf, shift);
   for(int j = 1; j <= strength; j++)
      if(candidate <= iHigh(symbol, tf, shift - j) || candidate <= iHigh(symbol, tf, shift + j)) return false;
   return true;
}

bool IsSwingLow(const string symbol, ENUM_TIMEFRAMES tf, int shift, int strength)
{
   if(shift < strength + 1) return false;
   double candidate = iLow(symbol, tf, shift);
   for(int j = 1; j <= strength; j++)
      if(candidate >= iLow(symbol, tf, shift - j) || candidate >= iLow(symbol, tf, shift + j)) return false;
   return true;
}

// Gets a confirmed swing that existed before `fromShift` (series indexing).
double LastSwing(const string symbol, ENUM_TIMEFRAMES tf, int fromShift, int strength, bool high, int maxBars = 300)
{
   int total = Bars(symbol, tf);
   int first = MathMax(fromShift + strength, strength + 1);
   int last = MathMin(total - strength - 1, first + maxBars);
   for(int s = first; s <= last; s++)
   {
      if(high && IsSwingHigh(symbol, tf, s, strength)) return iHigh(symbol, tf, s);
      if(!high && IsSwingLow(symbol, tf, s, strength)) return iLow(symbol, tf, s);
   }
   return EMPTY_VALUE;
}

int H4Direction(const string symbol, datetime at)
{
   int s = iBarShift(symbol, PERIOD_H4, at, false) + 1; // never inspect an open H4 bar
   if(s < InpH4EMAPeriod + 2) return 0;
   double lastHigh = LastSwing(symbol, PERIOD_H4, s, InpSwingStrength, true);
   double lastLow  = LastSwing(symbol, PERIOD_H4, s, InpSwingStrength, false);
   double close    = iClose(symbol, PERIOD_H4, s);
   if(lastHigh != EMPTY_VALUE && close > lastHigh) return 1;
   if(lastLow != EMPTY_VALUE && close < lastLow) return -1;

   // If market structure is not yet broken, use the H4 EMA slope as a conservative bias.
   double ema[];
   ArraySetAsSeries(ema, true);
   if(H4EmaHandle == INVALID_HANDLE || CopyBuffer(H4EmaHandle, 0, s, 2, ema) != 2) return 0;
   double now = ema[0];
   double old = ema[1];
   if(close > now && now > old) return 1;
   if(close < now && now < old) return -1;
   return 0;
}

bool HasH1BOS(const string symbol, datetime at, int direction)
{
   int current = iBarShift(symbol, PERIOD_H1, at, false) + 1;
   if(current < 2) return false;
   int last = MathMin(current + InpSetupExpiryH1Bars, Bars(symbol, PERIOD_H1) - InpSwingStrength - 2);
   for(int s = current; s <= last; s++)
   {
      double level = LastSwing(symbol, PERIOD_H1, s + 1, InpSwingStrength, direction > 0);
      if(level == EMPTY_VALUE) continue;
      if(direction > 0 && iClose(symbol, PERIOD_H1, s) > level) return true;
      if(direction < 0 && iClose(symbol, PERIOD_H1, s) < level) return true;
   }
   return false;
}

// Liquidity sweep: pierce the prior M15 range then close back inside it.
bool HasM15Sweep(const string symbol, datetime at, int direction)
{
   int s = iBarShift(symbol, PERIOD_M15, at, false) + 1;
   if(s + InpM15LiquidityLookback >= Bars(symbol, PERIOD_M15)) return false;
   double level = direction > 0
      ? iLow(symbol, PERIOD_M15, iLowest(symbol, PERIOD_M15, MODE_LOW, InpM15LiquidityLookback, s + 1))
      : iHigh(symbol, PERIOD_M15, iHighest(symbol, PERIOD_M15, MODE_HIGH, InpM15LiquidityLookback, s + 1));
   if(direction > 0) return iLow(symbol, PERIOD_M15, s) < level && iClose(symbol, PERIOD_M15, s) > level;
   return iHigh(symbol, PERIOD_M15, s) > level && iClose(symbol, PERIOD_M15, s) < level;
}

bool HasM5Confirmation(const string symbol, datetime at, int direction)
{
   int s = iBarShift(symbol, PERIOD_M5, at, false) + 1;
   if(s + InpM5BreakLookback >= Bars(symbol, PERIOD_M5)) return false;
   if(direction > 0)
      return iClose(symbol, PERIOD_M5, s) > iHigh(symbol, PERIOD_M5, iHighest(symbol, PERIOD_M5, MODE_HIGH, InpM5BreakLookback, s + 1));
   return iClose(symbol, PERIOD_M5, s) < iLow(symbol, PERIOD_M5, iLowest(symbol, PERIOD_M5, MODE_LOW, InpM5BreakLookback, s + 1));
}

bool HasM1Attack(const int i, const double &close[], const double &high[], const double &low[], int direction)
{
   if(i + InpM1BreakLookback >= ArraySize(close)) return false;
   double level = direction > 0 ? high[i + 1] : low[i + 1];
   for(int j = 2; j <= InpM1BreakLookback; j++)
   {
      if(direction > 0) level = MathMax(level, high[i + j]);
      else level = MathMin(level, low[i + j]);
   }
   return direction > 0 ? close[i] > level : close[i] < level;
}

int OnInit()
{
   if(_Period != PERIOD_M1) Print("MTF Liquidity Structure: use on an M1 chart.");
   SetIndexBuffer(0, BuyBuffer, INDICATOR_DATA);
   SetIndexBuffer(1, SellBuffer, INDICATOR_DATA);
   ArraySetAsSeries(BuyBuffer, true);
   ArraySetAsSeries(SellBuffer, true);
   PlotIndexSetInteger(0, PLOT_ARROW, 233);
   PlotIndexSetInteger(1, PLOT_ARROW, 234);
   H4EmaHandle = iMA(_Symbol, PERIOD_H4, InpH4EMAPeriod, 0, MODE_EMA, PRICE_CLOSE);
   if(H4EmaHandle == INVALID_HANDLE) return INIT_FAILED;
   IndicatorSetString(INDICATOR_SHORTNAME, "MTF Liquidity Structure (H4/H1/M15/M5/M1)");
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
   if(H4EmaHandle != INVALID_HANDLE) IndicatorRelease(H4EmaHandle);
}

int OnCalculate(const int rates_total, const int prev_calculated, const datetime &time[],
                const double &open[], const double &high[], const double &low[], const double &close[],
                const long &tick_volume[], const long &volume[], const int &spread[])
{
   if(rates_total < InpM1BreakLookback + 10) return 0;
   int start = rates_total - InpM1BreakLookback - 1;
   if(prev_calculated > 0) start = MathMin(start, rates_total - prev_calculated + 5);
   for(int i = start; i >= 1; i--) // index 0 is the live, unclosed M1 candle
   {
      BuyBuffer[i] = EMPTY_VALUE;
      SellBuffer[i] = EMPTY_VALUE;
      int direction = H4Direction(_Symbol, time[i]);
      if(direction == 0 || !HasH1BOS(_Symbol, time[i], direction) || !HasM15Sweep(_Symbol, time[i], direction)) continue;
      if(!HasM5Confirmation(_Symbol, time[i], direction) || !HasM1Attack(i, close, high, low, direction)) continue;
      if(direction > 0) BuyBuffer[i] = low[i] - InpArrowOffsetPoints * _Point;
      else SellBuffer[i] = high[i] + InpArrowOffsetPoints * _Point;
   }
   return rates_total;
}
