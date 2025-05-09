from datetime import datetime
from decimal import Decimal

from pyspark.sql import SparkSession
from pyspark.sql.types import (
    DecimalType,
    IntegerType,
    StructField,
    StructType,
    TimestampType,
)

from etl.layers.silver.fact_order_items_silver import FactOrderItemsSiverETL
from etl.utils.base_table import ETLDataSet


class TestFactOrderItemsSilverIntegration:
    """tests the full pipeline"""

    def test_transform_validate_load_read(self, spark: SparkSession):
        schema = StructType(
            [
                StructField("order_item_id", IntegerType(), True),
                StructField("order_id", IntegerType(), True),
                StructField("product_id", IntegerType(), True),
                StructField("seller_id", IntegerType(), True),
                StructField("quantity", IntegerType(), True),
                StructField("base_price", DecimalType(10, 2), True),
                StructField("tax", DecimalType(10, 2), True),
                StructField("created_ts", TimestampType(), True),
                StructField("etl_inserted", TimestampType(), True),
            ]
        )

        sample_data = [
            (
                1,
                100,
                500,
                10,
                2,
                Decimal(100.0),
                Decimal(10.0),
                datetime.now(),
                datetime.now(),
            )
        ]

        input_df = spark.createDataFrame(
            spark.sparkContext.parallelize(sample_data),
            schema,
        )

        order_items_dataset = ETLDataSet(
            "order_items",
            input_df,
            ["order_item_id"],
            "s3a://rainforest/delta/silver/fact_order_item",
            "delta",
            "rainforest",
            [],
        )

        etl_process = FactOrderItemsSiverETL(spark)

        transformed_dataset = etl_process.transform_upstream([order_items_dataset])

        is_valid = etl_process.validate(transformed_dataset)
        assert is_valid, "Data validation failed."

        etl_process.write(transformed_dataset)

        loaded_data = etl_process.read()

        expected_columns = [
            "order_item_id",
            "order_id",
            "product_id",
            "seller_id",
            "quantity",
            "base_price",
            "tax",
            "actual_price",
        ]

        expected_data = [
            (
                1,
                100,
                500,
                10,
                2,
                Decimal(100.0),
                Decimal(10.0),
                Decimal(90.0),
            )
        ]

        assert set(
            [
                c
                for c in loaded_data.current_data.columns
                if c not in ["created_ts", "etl_inserted"]
            ]
        ) == set(expected_columns), (
            "Loaded data columns=does not match expected columns"
        )

        actual_data = [
            (
                row["order_item_id"],
                row["order_id"],
                row["product_id"],
                row["seller_id"],
                row["quantity"],
                row["base_price"],
                row["tax"],
                row["actual_price"],
            )
            for row in loaded_data.current_data.collect()
        ]

        assert actual_data == expected_data, "Loaded data does not match expected data"
