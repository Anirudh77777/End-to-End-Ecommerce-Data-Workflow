from datetime import datetime
from typing import Dict, List, Optional, Type

from pyspark.sql import SparkSession
from pyspark.sql.functions import col, lit
from pyspark.sql.functions import mean as spark_mean
from pyspark.sql.functions import sum as spark_sum
from etl.layers.gold.wide_orders_gold import WideOrdersGoldETL
from etl.utils.base_table import ETLDataSet, TableETL


class DailyOrderMetricsGoldETL(TableETL):
    """
    DailyOrderMetricsGoldETL is a class that extends the TableETL base class to perform ETL operations for daily order metrics in the gold layer of a data lake.
    Attributes:
        spark (SparkSession): The Spark session to use for ETL operations.
        upstream_tables (Optional[List[Type[TableETL]]]): List of upstream ETL table classes to extract data from.
        name (str): The name of the ETL table.
        primary_keys (List[str]): List of primary key columns for the ETL table.
        storage_path (str): The storage path for the ETL table data.
        data_format (str): The data format for the ETL table data.
        database (str): The database name for the ETL table.
        partition_keys (List[str]): List of partition key columns for the ETL table.
        run_upstream (bool): Flag to indicate whether to run upstream ETL processes.
        write_data (bool): Flag to indicate whether to write data to storage.
    Methods:
        extract_upstream(self) -> List[ETLDataSet]:
        transform_upstream(self, upstream_datasets: List[ETLDataSet]) -> ETLDataSet:
        read(self, partition_values: Optional[Dict[str, str]] = None) -> ETLDataSet:
    """

    def __init__(
        self,
        spark: SparkSession,
        upstream_tables: Optional[List[Type[TableETL]]] = [WideOrdersGoldETL],
        name: str = "daily_order_metrics",
        primary_keys: List[str] = ["order_ts"],
        storage_path: str = "s3a://rainforest/delta/gold/daily_order_metrics",
        data_format: str = "delta",
        database: str = "rainforest",
        partition_keys: List[str] = ["etl_inserted"],
        run_upstream=True,
        write_data=True,
    ) -> None:
        super().__init__(
            spark,
            upstream_tables,
            name,
            primary_keys,
            storage_path,
            data_format,
            database,
            partition_keys,
            run_upstream,
            write_data,
        )

    def extract_upstream(self) -> List[ETLDataSet]:
        """
        Extracts data from upstream ETL tables.
        This method initializes each upstream ETL table class, runs the ETL process
        if specified, and reads the data from each table. The extracted data is
        collected into a list of ETLDataSet objects.
        Returns:
            List[ETLDataSet]: A list of datasets extracted from the upstream ETL tables.
        """

        upstream_etl_datasets = []
        for table_etl_class in self.upstream_tables:
            table = table_etl_class(
                spark=self.spark,
                run_upstream=self.run_upstream,
                write_data=self.write_data,
            )
            if self.run_upstream:
                table.run()

            upstream_etl_datasets.append(table.read())

        return upstream_etl_datasets

    def transform_upstream(self, upstream_datasets: List[ETLDataSet]) -> ETLDataSet:
        """
        Transforms the upstream datasets to generate daily order metrics.
        Args:
            upstream_datasets (List[ETLDataSet]): List of upstream datasets where the first dataset contains the wide orders data.
        Returns:
            ETLDataSet: A new ETLDataSet containing the daily order metrics.
        The transformation includes:
            - Casting the 'order_ts' column to 'order_date'.
            - Filtering the data to include only active orders.
            - Aggregating the data by 'order_date' to calculate the sum and mean of 'total_price'.
            - Adding a column 'etl_inserted' with the current timestamp.
        """

        wide_orders_data = upstream_datasets[0].current_data
        wide_orders_data = wide_orders_data.withColumn(
            "order_date", col("order_ts").cast("date")
        )

        wide_orders_data = wide_orders_data.filter(col("is_active"))

        daily_metrics_data = wide_orders_data.groupBy("order_date").agg(
            spark_sum("total_price").alias("total_price_sum"),
            spark_mean("total_price").alias("total_price_mean"),
        )

        current_timestamp = datetime.now()

        daily_metrics_data = daily_metrics_data.withColumn(
            "etl_inserted", lit(current_timestamp)
        )

        etl_dataset = ETLDataSet(
            name=self.name,
            current_data=daily_metrics_data,
            primary_keys=self.primary_keys,
            storage_path=self.storage_path,
            data_format=self.data_format,
            database=self.database,
            partition_keys=self.partition_keys,
        )

        self.current_data = etl_dataset.current_data

        return etl_dataset

    def read(self, partition_values: Optional[Dict[str, str]] = None) -> ETLDataSet:
        """
        Reads data from the specified storage path and returns it as an ETLDataSet.
        Args:
            partition_values (Optional[Dict[str, str]]): A dictionary of partition key-value pairs to filter the data.
                                                         If None, the latest partition will be used.
        Returns:
            ETLDataSet: An object containing the selected data, metadata, and configuration details.
        Raises:
            Exception: If there is an error reading the data or filtering the partitions.
        """

        selected_columns = [
            col("order_date"),
            col("total_price_sum"),
            col("total_price_mean"),
            col("etl_inserted"),
        ]

        if not self.write_data:
            return ETLDataSet(
                name=self.name,
                current_data=self.current_data.select(selected_columns),
                primary_keys=self.primary_keys,
                storage_path=self.storage_path,
                data_format=self.data_format,
                database=self.database,
                partition_keys=self.partition_keys,
            )

        elif partition_values:
            partition_filter = " AND".join(
                [f"{k} = '{v}'" for k, v in partition_values.items()]
            )
        else:
            latest_partition = (
                self.spark.read.format(self.data_format)
                .load(self.storage_path)
                .selectExpr("max(etl_inserted)")
                .collect()[0][0]
            )

            partition_filter = f"etl_inserted = '{latest_partition}'"

        fact_order_data = (
            self.spark.read.format(self.data_format)
            .load(self.storage_path)
            .filter(partition_filter)
        )

        fact_order_data = fact_order_data.select(selected_columns)

        etl_dataset = ETLDataSet(
            name=self.name,
            current_data=fact_order_data,
            primary_keys=self.primary_keys,
            storage_path=self.storage_path,
            data_format=self.data_format,
            database=self.database,
            partition_keys=self.partition_keys,
        )

        return etl_dataset
