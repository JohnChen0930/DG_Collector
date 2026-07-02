DGAnalyzer 2.0

執行：
python analyzer.py --db history.db

查詢 Pattern：
python analyzer.py --db history.db --query RB01 BBBP

查詢某桌目前推薦：
python analyzer.py --db history.db --recommend RB01

輸出資料夾：
reports_20/

重點修正：
1. 不再只用 shoeId 分組，改用 tableName + shoeId。
2. Tie 不參與 Pattern，也不會中斷 Pattern。
3. Pattern Engine 獨立，之後 AutoBet/Dashboard 可以直接呼叫。
