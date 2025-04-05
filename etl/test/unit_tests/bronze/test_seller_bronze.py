from etl.layers.bronze.seller import SellerBronzeETL
from etl.utils.base_table import ETLDataSet


class TestSellerBronzeETL:
    """
    Test suite for the SellerBronzeETL class.
    This test suite contains unit tests for the methods of the SellerBronzeETL class, which is responsible for
    extracting and transforming data in the ETL pipeline.
    Classes:
        TestSellerBronzeETL: Contains unit tests for the SellerBronzeETL class.
    Methods:
        test_extract_upstream(spark):
        test_transform_upstream(spark):
    """

    def test_extract_upstream(self, spark):
        """
        Test the extract_upstream method of the SellerBronzeETL class.
        This test initializes an instance of the SellerBronzeETL class with a Spark session,
        calls the extract_upstream method, and asserts that the first    element in the resulting
        dataset has a name attribute equal to "seller".
        Args:
            spark (SparkSession): The Spark session to be used for the test.
        Asserts:
            The name attribute of the first element in the dataset returned by extract_upstream
            is equal to "seller".
        """

        seller_table = SellerBronzeETL(spark=spark)
        seller_table_dataset = seller_table.extract_upstream()

        assert seller_table_dataset[0].name == "seller"

    def test_transform_upstream(self, spark):
        """
        Test the `transform_upstream` method of the `SellerBronzeETL` class.
        This test verifies that the `transform_upstream` method correctly transforms the upstream dataset by:
        1. Adding a new column `etl_inserted` to the DataFrame.
        2. Ensuring the schema of the transformed DataFrame includes the new column.
        3. Verifying that the data in the original columns remains unchanged.
        Args:
            spark (SparkSession): The Spark session to use for creating DataFrames.
        Steps:
        1. Create a sample DataFrame with predefined data and schema.
        2. Instantiate the `SellerBronzeETL` class.
        3. Create an `ETLDataSet` object with the sample DataFrame.
        4. Call the `transform_upstream` method with the `ETLDataSet` object.
        5. Assert that the new column `etl_inserted` is added to the DataFrame.
        6. Assert that the schema of the transformed DataFrame includes the new column.
        7. Assert that the data in the original columns remains unchanged.
        """

        sample_data = [
            (
                1,
                "user_1",
                "2024-01-01",
                "2024-01-01",
                "Updater A",
                "2024-01-01",
            ),
            (
                2,
                "user_2",
                "2024-01-02",
                "2024-01-02",
                "Updater B",
                "2024-01-02",
            ),
        ]
        schema = [
            "seller_id",
            "user_id",
            "first_time_sold_timestamp",
            "created_ts",
            "last_updated_by",
            "last_updated_ts",
        ]

        upstream_df = spark.createDataFrame(sample_data, schema=schema)

        seller_table = SellerBronzeETL(spark=spark)

        upstream_dataset = ETLDataSet(
            name=seller_table.name,
            current_data=upstream_df,
            primary_keys=seller_table.primary_keys,
            storage_path=seller_table.storage_path,
            data_format=seller_table.data_format,
            database=seller_table.database,
            partition_keys=seller_table.partition_keys,
        )

        transformed_datasets = seller_table.transform_upstream([upstream_dataset])

        assert "etl_inserted" in transformed_datasets.current_data.columns

        expected_schema = set(schema + ["etl_inserted"])
        assert set(transformed_datasets.current_data.columns) == expected_schema

        transformed_dataset = transformed_datasets.current_data.select(schema)
        assert transformed_dataset.collect() == upstream_df.collect()
