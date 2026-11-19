from flask import Flask, request, jsonify
import pymysql
import time

app = Flask(__name__)

DB_HOST = "hotel-db"
DB_USER = "hoteluser"
DB_PASSWORD = "Hotel@123"
DB_NAME = "hoteldb"

def get_db():
    return pymysql.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        cursorclass=pymysql.cursors.DictCursor
    )

def initialize_db():
    for attempt in range(30):
        try:
            conn = get_db()
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS rooms (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        name VARCHAR(100) NOT NULL,
                        price DECIMAL(10,2) NOT NULL
                    )
                """)

                cur.execute("""
                    CREATE TABLE IF NOT EXISTS bookings (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        guest_name VARCHAR(100) NOT NULL,
                        email VARCHAR(150) NOT NULL,
                        room_id INT NOT NULL,
                        check_in DATE NOT NULL,
                        check_out DATE NOT NULL,
                        guests INT NOT NULL,
                        FOREIGN KEY (room_id) REFERENCES rooms(id)
                    )
                """)

                cur.execute("SELECT COUNT(*) AS total FROM rooms")
                if cur.fetchone()["total"] == 0:
                    cur.executemany("""
                        INSERT INTO rooms (name, price)
                        VALUES (%s, %s)
                    """, [
                        ("Deluxe Room", 2500),
                        ("Premium Room", 4000),
                        ("Luxury Suite", 6000)
                    ])

            conn.commit()
            conn.close()
            print("Database initialized successfully")
            return
        except Exception as e:
            print("Waiting for MySQL:", e)
            time.sleep(3)

    raise RuntimeError("Could not connect to MySQL")

@app.route("/api/rooms", methods=["GET"])
def rooms():
    conn = get_db()
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM rooms")
        result = cur.fetchall()
    conn.close()
    return jsonify(result)

@app.route("/api/bookings", methods=["POST"])
def create_booking():
    data = request.get_json(silent=True) or {}

    required = [
        "guest_name", "email", "room_id",
        "check_in", "check_out", "guests"
    ]

    if any(not data.get(key) for key in required):
        return jsonify({"error": "All fields are required"}), 400

    try:
        from datetime import date

        check_in = date.fromisoformat(data["check_in"])
        check_out = date.fromisoformat(data["check_out"])
        guests = int(data["guests"])
        room_id = int(data["room_id"])

        if check_in < date.today() or check_out <= check_in:
            return jsonify({"error": "Invalid booking dates"}), 400

        if guests < 1 or guests > 10:
            return jsonify({"error": "Guests must be between 1 and 10"}), 400

        conn = get_db()

        with conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM rooms WHERE id=%s",
                (room_id,)
            )
            if not cur.fetchone():
                conn.close()
                return jsonify({"error": "Room not found"}), 404

            cur.execute("""
                SELECT id FROM bookings
                WHERE room_id=%s
                AND check_in < %s
                AND check_out > %s
            """, (room_id, check_out, check_in))

            if cur.fetchone():
                conn.close()
                return jsonify({"error": "Room is already booked for these dates"}), 409

            cur.execute("""
                INSERT INTO bookings
                (guest_name, email, room_id, check_in, check_out, guests)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (
                data["guest_name"],
                data["email"],
                room_id,
                check_in,
                check_out,
                guests
            ))

            booking_id = cur.lastrowid

        conn.commit()
        conn.close()

        return jsonify({
            "message": "Booking successful!",
            "booking_id": booking_id
        }), 201

    except (ValueError, TypeError):
        return jsonify({"error": "Invalid input"}), 400
    except Exception:
        app.logger.exception("Booking failed")
        return jsonify({"error": "Booking could not be completed"}), 500

@app.route("/api/bookings", methods=["GET"])
def get_bookings():
    conn = get_db()
    with conn.cursor() as cur:
        cur.execute("""
            SELECT b.id, b.guest_name, b.email,
                   r.name AS room_name, b.check_in,
                   b.check_out, b.guests
            FROM bookings b
            JOIN rooms r ON b.room_id = r.id
            ORDER BY b.id DESC
        """)
        result = cur.fetchall()

    conn.close()

    for booking in result:
        booking["check_in"] = str(booking["check_in"])
        booking["check_out"] = str(booking["check_out"])

    return jsonify(result)

if __name__ == "__main__":
    initialize_db()
    app.run(host="0.0.0.0", port=5000)
