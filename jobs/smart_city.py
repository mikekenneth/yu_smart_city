from config import configuration
from pyspark.sql import SparkSession, DataFrame
from pyspark.sql.functions import from_json, col
from pyspark.sql.types import StructType, StructField, StringType, IntegerType, TimestampType, DoubleType


def main():
    spark = (
        SparkSession.builder.appName("SmartCityStreaming")
        .config(
            "spark.jars.packages",
            "org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.1,"
            + "org.apache.hadoop:hadoop-aws:3.3.6,"
            + "com.amazonaws:aws-java-sdk:1.12.629",
        )
        .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem")
        .config("spark.hadoop.fs.s3a.access.key", configuration["MINIO_ACCESS_KEY"])
        .config("spark.hadoop.fs.s3a.secret.key", configuration["MINIO_SECRET_KEY"])
        .config("spark.hadoop.fs.s3a.endpoint", configuration["MINIO_ENDPOINT"])
        .config("spark.hadoop.fs.s3a.connection.ssl.enabled", "false")
        .config("spark.hadoop.fs.s3a.path.style.access", "true")
        .config("spark.hadoop.fs.s3a.attempts.maximum", "5")
        .config("spark.hadoop.fs.s3a.connection.establish.timeout", "5000")
        .config("spark.hadoop.fs.s3a.connection.timeout", "10000")
        .getOrCreate()
    )

    # Set the log output to minize the console output
    spark.sparkContext.setLogLevel("WARN")

    # Vehicle Schema
    vehicleSchema = StructType(
        [
            StructField(name="id", dataType=StringType(), nullable=True),
            StructField(name="deviceId", dataType=StringType(), nullable=True),
            StructField(name="timestamp", dataType=TimestampType(), nullable=True),
            StructField(name="location", dataType=StringType(), nullable=True),
            StructField(name="speed", dataType=DoubleType(), nullable=True),
            StructField(name="direction", dataType=StringType(), nullable=True),
            StructField(name="make", dataType=StringType(), nullable=True),
            StructField(name="model", dataType=StringType(), nullable=True),
            StructField(name="year", dataType=IntegerType(), nullable=True),
            StructField(name="fuelType", dataType=StringType(), nullable=True),
        ]
    )

    # GPS Schema
    gpsSchema = StructType(
        [
            StructField(name="id", dataType=StringType(), nullable=True),
            StructField(name="deviceId", dataType=StringType(), nullable=True),
            StructField(name="timestamp", dataType=TimestampType(), nullable=True),
            StructField(name="speed", dataType=DoubleType(), nullable=True),
            StructField(name="direction", dataType=StringType(), nullable=True),
            StructField(name="vehicleType", dataType=StringType(), nullable=True),
        ]
    )

    # Traffic Camera Schema
    trafficSchema = StructType(
        [
            StructField(name="id", dataType=StringType(), nullable=True),
            StructField(name="deviceId", dataType=StringType(), nullable=True),
            StructField(name="cameraId", dataType=StringType(), nullable=True),
            StructField(name="timestamp", dataType=TimestampType(), nullable=True),
            StructField(name="location", dataType=StringType(), nullable=True),
            StructField(name="snapshot", dataType=StringType(), nullable=True),
        ]
    )

    # Weather Camera Schema
    weatherSchema = StructType(
        [
            StructField(name="id", dataType=StringType(), nullable=True),
            StructField(name="deviceId", dataType=StringType(), nullable=True),
            StructField(name="timestamp", dataType=TimestampType(), nullable=True),
            StructField(name="location", dataType=StringType(), nullable=True),
            StructField(name="temperature", dataType=DoubleType(), nullable=True),
            StructField(name="weatherCondition", dataType=StringType(), nullable=True),
            StructField(name="precipitation", dataType=DoubleType(), nullable=True),
            StructField(name="windSpeed", dataType=DoubleType(), nullable=True),
            StructField(name="humidity", dataType=DoubleType(), nullable=True),
            StructField(name="airQualityindex", dataType=DoubleType(), nullable=True),
        ]
    )

    # Emergency Camera Schema
    emergencySchema = StructType(
        [
            StructField(name="id", dataType=StringType(), nullable=True),
            StructField(name="deviceId", dataType=StringType(), nullable=True),
            StructField(name="incidendId", dataType=StringType(), nullable=True),
            StructField(name="timestamp", dataType=TimestampType(), nullable=True),
            StructField(name="location", dataType=StringType(), nullable=True),
            StructField(name="type", dataType=StringType(), nullable=True),
            StructField(name="status", dataType=StringType(), nullable=True),
            StructField(name="description", dataType=StringType(), nullable=True),
        ]
    )

    def read_kafka_topic(topic: str, schema: StructType):
        return (
            spark.readStream.format("kafka")
            .option(
                "kafka.bootstrap.servers", "kafka-kraft:29092"
            )  # TODO: Resolve Broker unavailable error with Spark
            .option("subscribe", topic)
            .option("startingOffsets", "earliest")
            .load()
            .selectExpr("CAST(value as STRING)")
            .select(from_json(col("value"), schema).alias("data"))
            .select("data.*")
            .withWatermark("timestamp", "2 minutes")
        )

    def streamWriter(inputDF: DataFrame, checkpointFolder: str, output_path: str):
        return (
            inputDF.writeStream.format("parquet")
            .option("checkpointLocation", checkpointFolder)
            .option("path", output_path)
            .outputMode("append")
            .start()
        )

    vehicleDF = read_kafka_topic(topic="vehicle_data", schema=vehicleSchema).alias("vehicle")
    gpsDF = read_kafka_topic(topic="gps_data", schema=gpsSchema).alias("gps")
    trafficDF = read_kafka_topic(topic="traffic_data", schema=trafficSchema).alias("traffic")
    weatherDF = read_kafka_topic(topic="weather_data", schema=weatherSchema).alias("weather")
    emergencyDF = read_kafka_topic(topic="emergency_data", schema=emergencySchema).alias("emergency")

    # Join all the DF

    query1 = streamWriter(
        inputDF=vehicleDF,
        checkpointFolder=f"s3a://{configuration['MINIO_BUCKET']}/checkpoints/vehicle_data",
        output_path=f"s3a://{configuration['MINIO_BUCKET']}/data/vehicle_data",
    )

    query2 = streamWriter(
        inputDF=gpsDF,
        checkpointFolder=f"s3a://{configuration['MINIO_BUCKET']}/checkpoints/gps_data",
        output_path=f"s3a://{configuration['MINIO_BUCKET']}/data/gps_data",
    )

    query3 = streamWriter(
        inputDF=trafficDF,
        checkpointFolder=f"s3a://{configuration['MINIO_BUCKET']}/checkpoints/traffic_data",
        output_path=f"s3a://{configuration['MINIO_BUCKET']}/data/traffic_data",
    )

    query4 = streamWriter(
        inputDF=weatherDF,
        checkpointFolder=f"s3a://{configuration['MINIO_BUCKET']}/checkpoints/weather_data",
        output_path=f"s3a://{configuration['MINIO_BUCKET']}/data/weather_data",
    )

    query5 = streamWriter(
        inputDF=emergencyDF,
        checkpointFolder=f"s3a://{configuration['MINIO_BUCKET']}/checkpoints/emergency_data",
        output_path=f"s3a://{configuration['MINIO_BUCKET']}/data/emergency_data",
    )

    query5.awaitTermination()


if __name__ == "__main__":
    main()
