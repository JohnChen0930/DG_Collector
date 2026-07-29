const data = Laya.stage.getChildAt(0).gameDataMan.dataInfo;

return JSON.parse(JSON.stringify(
    data.map(table => ({
        tableId: table.tableId,
        tableName: table.tableName || "",
        gameName: table.gameName || "",
        gameNo: table.gameNo || "",
        playId: table.playId || 0,
        stateId: table.stateId || 0,
        result: table.result || "",
        poker: table.poker || "",
        winPoint: table.winPoint || "",
        roadLen: table.roadArray ? table.roadArray.length : 0,
        latest: (
            table.roadArray &&
            table.roadArray.length > 0
        )
            ? table.roadArray[table.roadArray.length - 1]
            : null
    }))
));