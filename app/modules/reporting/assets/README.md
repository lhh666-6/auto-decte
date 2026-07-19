# 受控固定格式报表资产

`legacy_timekeeping_daily.xlsx` 由用户提供的项目根目录 `计时工日工资计算表.xls` 只读转换而来，用于 `TIMEKEEPING_DAILY_FIXED:1`。

- 原 `.xls` SHA-256：`b910258d3489ecd9597cf3903b47148413089c607ecfd2957362445441ece4ff`
- 受控 `.xlsx` SHA-256：`2757f427bca00dcb0f87adc854762925a601fdf3b5cd970b1056766fc30068dd`
- 转换时确认：单工作表 `计时`，无公式、无外部链接；源文件转换前后哈希一致。

运行时只读取哈希匹配的 `.xlsx` 资产，生成新文件，不覆盖此资产或原 `.xls`。
