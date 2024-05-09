import os
import time
import uuid
import random
import simplejson as json
from confluent_kafka import SerializingProducer
from datetime import datetime, timedelta

LONDON_COORDINATES = {
    "latitude": 51.5074,
    "longitude": -0.1278,
}

BIRMINGHAM_COORDINATES = {
    "latitude": 52.4862,
    "longitude": -1.8904,
}

# Calculate the movement increments
LATITUDE_INCREMENT = (BIRMINGHAM_COORDINATES["latitude"] - LONDON_COORDINATES["latitude"]) / 100
LONGITUDE_INCREMENT = (BIRMINGHAM_COORDINATES["longitude"] - LONDON_COORDINATES["longitude"]) / 100

# Environment Variables for configuration
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
VEHICLE_TOPIC = os.getenv("VEHICLE_TOPIC", "vehicle_data")
GPS_TOPIC = os.getenv("GPS_TOPIC", "gsp_data")
TRAFFIC_TOPIC = os.getenv("TRAFFIC_TOPIC", "traffic_data")
WEATHER_TOPIC = os.getenv("WEATHER_TOPIC", "weather_data")
EMERGENCY_TOPIC = os.getenv("EMERGENCY_TOPIC", "emergency_data")

random.seed(42)
start_time = datetime.now()
start_location = LONDON_COORDINATES.copy()


def get_next_time():
    global start_time
    start_time += timedelta(seconds=random.randint(20, 60))
    return start_time


def generate_gps_data(device_id: str, timestamp: str, vehicle_type: str = "private"):
    return {
        "id": uuid.uuid4(),
        "deviceId": device_id,
        "timestamp": timestamp,
        "speed": random.uniform(0, 40),
        "direction": "North-East",
        "vehicleType": vehicle_type,
    }


def generate_traffic_camera_data(device_id: str, timestamp: str, location: str, camera_id: str):
    return {
        "id": uuid.uuid4(),
        "deviceId": device_id,
        "cameraId": camera_id,
        "timestamp": timestamp,
        "location": location,
        "snapshot": "Base64EncodedString",
    }


def generate_weather_data(device_id: str, timestamp: str, location: str):
    return {
        "id": uuid.uuid4(),
        "deviceId": device_id,
        "timestamp": timestamp,
        "location": location,
        "temperature": random.uniform(-5, 32),
        "weatherCondition": random.choice(["Sunny", "Cloudy", "Rain", "Snow"]),
        "precipitation": random.uniform(0, 25),
        "windSpeed": random.uniform(0, 100),
        "humidity": random.uniform(0, 100),  # Percentage
        "airQualityindex": random.uniform(0, 500),
    }


def generate_emergency_incident_data(device_id: str, timestamp: str, location: str):
    return {
        "id": uuid.uuid4(),
        "deviceId": device_id,
        "incidendId": uuid.uuid4(),
        "timestamp": timestamp,
        "location": location,
        "type": random.choice(["Accident", "Fire", "Medical", "Police"]),
        "status": random.choice(["Active", "Resolved"]),
        "description": "Incident Description",
    }


def simulate_vehicle_movement():
    global start_location

    # Move towards destination
    start_location["latitude"] += LATITUDE_INCREMENT
    start_location["longitude"] += LONGITUDE_INCREMENT

    # Add randomness to simulate actual road travel
    start_location["latitude"] += random.uniform(-0.0005, 0.0005)
    start_location["longitude"] += random.uniform(-0.0005, 0.0005)

    return start_location


def generate_vehicle_data(device_id: str):
    location = simulate_vehicle_movement()
    return {
        "id": uuid.uuid4(),
        "deviceId": device_id,
        "timestamp": get_next_time().isoformat(),
        "location": (location["latitude"], location["longitude"]),
        "speed": random.uniform(10, 40),
        "direction": "North-East",
        "make": "Range-Rover",
        "model": "Velar",
        "year": 2024,
        "fuelType": "Hybrid",
    }


def json_serializer(obj: object):
    if isinstance(obj, uuid.UUID):
        return str(obj)
    raise TypeError(f"Object if type {obj.__class__.__name__} is not JSON serializable")


def delivery_report(err, msg):
    if err is not None:
        print(f"Message delivery failed: {err}")
    else:
        print(f"Message delivery to: {msg.topic()} [Partition: {msg.partition()}]")


def produce_data_to_kafka(producer: SerializingProducer, topic: str, data: dict):
    producer.produce(
        topic=topic,
        key=str(data["id"]),
        value=json.dumps(data, default=json_serializer).encode("utf-8"),
        on_delivery=delivery_report,
    )

    producer.flush()


def simulate_journey(producer: SerializingProducer, device_id: str):
    while True:
        vehicle_data = generate_vehicle_data(device_id=device_id)
        gps_data = generate_gps_data(device_id=device_id, timestamp=vehicle_data["timestamp"])
        traffic_camera_data = generate_traffic_camera_data(
            device_id=device_id,
            timestamp=vehicle_data["timestamp"],
            location=vehicle_data["location"],
            camera_id="Nikon-Cam123",
        )
        weather_data = generate_weather_data(
            device_id=device_id, timestamp=vehicle_data["timestamp"], location=vehicle_data["location"]
        )
        emergency_incident_data = generate_emergency_incident_data(
            device_id=device_id, timestamp=vehicle_data["timestamp"], location=vehicle_data["location"]
        )

        # Stop the tracking when we reach destination
        if (
            vehicle_data["location"][0] >= BIRMINGHAM_COORDINATES["latitude"]
            and vehicle_data["location"][1] >= BIRMINGHAM_COORDINATES["longitude"]
        ):
            print("Vehicle has reached Destination.\nSIMULATION ENDING...")
            break

        # Produce Data to kafka
        produce_data_to_kafka(producer=producer, topic=VEHICLE_TOPIC, data=vehicle_data)
        produce_data_to_kafka(producer=producer, topic=GPS_TOPIC, data=gps_data)
        produce_data_to_kafka(producer=producer, topic=TRAFFIC_TOPIC, data=traffic_camera_data)
        produce_data_to_kafka(producer=producer, topic=WEATHER_TOPIC, data=weather_data)
        produce_data_to_kafka(producer=producer, topic=EMERGENCY_TOPIC, data=emergency_incident_data)

        time.sleep(5)  # Every 5 seconds


if __name__ == "__main__":
    producer_config = {
        "bootstrap.servers": KAFKA_BOOTSTRAP_SERVERS,
        "error_cb": lambda err: print(f"Kafka Error:{err}"),
    }

    producer = SerializingProducer(conf=producer_config)

    try:
        simulate_journey(producer, "Vehicle-Mike123")
    except KeyboardInterrupt:
        print("Simulation ended by the user")
    except Exception as e:
        print(f"Unexpected Error occurred: {e}")
