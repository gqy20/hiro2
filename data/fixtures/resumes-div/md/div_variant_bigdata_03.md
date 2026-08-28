## 基本信息
- 姓名：张若愚 | 常驻城市：北京
- 电话：138****0000 | 邮箱：name@example.com
- 教育背景：南京邮电大学 · 电子信息工程（2018-2022）
- 证书：TOEFL 105

## 技能
- 计算引擎：Spark 3.4（PySpark 写过ETL，踩过shuffle倾斜的坑）、Flink 1.17（搞过CEP和窗口聚合，调过checkpoint超时）
- 数仓工具：Hive on Tez 用得最顺手，写过UDF；dbt 1.6 做ods→dwd的测试和文档自动生成
- 存储/调度：ClickHouse 23.8 搞过明细表物化视图，Airflow 2.7 搭过DAG依赖和重跑策略；Iceberg 1.4 在调研阶段，搞过分区演进

## 技能清单
- 语言：Python 3.10（pandas/ numpy / scipy）、SQL（复杂窗口函数+基于代价优化理解）
- 实时链路：Kafka → Flink → ClickHouse，状态后端用RocksDB
- 数据质量：Great Expectations 做主键唯一性/空值率校验
- 数仓建模：维度建模（缓慢变化维）+ 数据湖湖仓一体（Iceberg 1.4）

## 项目经历
**实时用户行为漏斗（Flink + ClickHouse）** | 2023.06-至今
- 基于Flink 1.17消费埋点Kafka流，用event-time和watermark处理乱序，搞了滑动窗口漏斗计算，支持路径正则匹配（A→B→C→D）
- 将结果sink到ClickHouse 23.8的ReplacingMergeTree，用物化视图做分钟级预聚合，查询p95<200ms
- 上线后踩过Flink背压导致checkpoint超时，用反压监控+调节buffer大小解决

**离线数仓分层重构（Spark + Hive）** | 2022.09-2023.05
- 将原有Hive表按dwd/dws/ads重建模，用Spark 3.4重跑历史任务，采用动态分区+sort merge join优化，任务时间从6h降到2.5h
- 引入dbt 1.6管理SQL，自动生成血缘图和数据测试，支持增量incremental策略
- 存量数据通过Iceberg 1.4的time travel做回溯对比验证

## 工作经历
**虾皮（Shopee） | 大数据开发工程师** | 2023.06-至今
- 负责推荐系统特征实时入仓，维护Flink作业和告警，日均处理20亿条消息
- 优化离线特征生产链路，P99延迟降低40%

**旷视科技 | 数据开发实习生→工程师** | 2021.06-2023.05
- 参与摄像头日志数仓建设，用Hive on Tez编写ETL，处理设备状态指标
- 独立搭建Airflow调度系统，支持200+个周期任务，解决任务依赖竞争

## 教育背景
**南京邮电大学 · 电子信息工程** | 2018-2022
- 全国大学生英语竞赛二等奖，天池大数据竞赛（电商用户行为预测）top10%，自学Java/Python并转向数据方向

## 证书
- TOEFL 105
