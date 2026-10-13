//+------------------------------------------------------------------+
//| Cria/atualiza um símbolo personalizado a partir de um CSV de     |
//| barras M1 (pasta Common\Files). Somente dados: não envia ordens. |
//| CSV: time,open,high,low,close,tick_volume,spread (time = epoch   |
//| já no relógio do servidor; spread em pontos).                    |
//+------------------------------------------------------------------+
#property script_show_inputs
#property strict

input string CustomName   = "XAUUSD.dk";
input string OriginSymbol = "XAUUSD.s";
input string GroupPath    = "Research\\Dukascopy";
input string CsvFile      = "XAUUSD_dk_M1.csv";
input string StatusFile   = "XAUUSD_dk_import_status.txt";
input bool   CloseTerminal = true;

void Status(const string text)
  {
   int h = FileOpen(StatusFile, FILE_WRITE | FILE_TXT | FILE_ANSI | FILE_COMMON);
   if(h != INVALID_HANDLE)
     {
      FileWriteString(h, text);
      FileClose(h);
     }
   Print("IMPORT STATUS: ", text);
  }

void OnStart()
  {
   bool exists = false;
   if(!SymbolExist(CustomName, exists))
     {
      if(!CustomSymbolCreate(CustomName, GroupPath, OriginSymbol))
        {
         Status("ERROR create " + IntegerToString(GetLastError()));
         if(CloseTerminal) TerminalClose(1);
         return;
        }
     }
   // Recomeça do zero: uma importação anterior com erro não pode sobrar no histórico.
   CustomRatesDelete(CustomName, 0, LONG_MAX);
   int h = FileOpen(CsvFile, FILE_READ | FILE_CSV | FILE_ANSI | FILE_COMMON, ',');
   if(h == INVALID_HANDLE)
     {
      Status("ERROR open csv " + IntegerToString(GetLastError()));
      if(CloseTerminal) TerminalClose(1);
      return;
     }
   // cabeçalho
   for(int c = 0; c < 7; c++) FileReadString(h);

   MqlRates batch[];
   ArrayResize(batch, 100000);
   int n = 0;
   long total = 0;
   datetime first = 0, last = 0;
   while(!FileIsEnding(h))
     {
      string t = FileReadString(h);
      if(t == "") break;
      MqlRates r;
      r.time = (datetime)StringToInteger(t);
      r.open = StringToDouble(FileReadString(h));
      r.high = StringToDouble(FileReadString(h));
      r.low = StringToDouble(FileReadString(h));
      r.close = StringToDouble(FileReadString(h));
      r.tick_volume = StringToInteger(FileReadString(h));
      r.spread = (int)StringToInteger(FileReadString(h));
      r.real_volume = 0;
      if(first == 0) first = r.time;
      last = r.time;
      batch[n++] = r;
      if(n == ArraySize(batch))
        {
         if(CustomRatesUpdate(CustomName, batch) < 0)
           {
            Status("ERROR update " + IntegerToString(GetLastError()));
            FileClose(h);
            if(CloseTerminal) TerminalClose(1);
            return;
           }
         total += n;
         n = 0;
        }
     }
   FileClose(h);
   if(n > 0)
     {
      ArrayResize(batch, n);
      if(CustomRatesUpdate(CustomName, batch) < 0)
        {
         Status("ERROR update " + IntegerToString(GetLastError()));
         if(CloseTerminal) TerminalClose(1);
         return;
        }
      total += n;
     }
   Status(StringFormat("OK %s rows=%I64d first=%s last=%s", CustomName, total,
                       TimeToString(first, TIME_DATE | TIME_MINUTES), TimeToString(last, TIME_DATE | TIME_MINUTES)));
   if(CloseTerminal) TerminalClose(0);
  }
