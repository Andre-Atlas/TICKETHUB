# 🎟️ TicketHub

### Full-Stack Event Management System
**A robust ticket reservation platform featuring a Python backend with hybrid database architecture.**

![Python](https://img.shields.io/badge/Python-3.10%2B-blue?style=for-the-badge&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi)
![Swift](https://img.shields.io/badge/Swift-FA7343?style=for-the-badge&logo=swift&logoColor=white)
![MySQL](https://img.shields.io/badge/MySQL-4479A1?style=for-the-badge&logo=mysql&logoColor=white)
![Redis](https://img.shields.io/badge/Redis-DC382D?style=for-the-badge&logo=redis&logoColor=white)

---

## 📖 About the Project

**TicketHub** is a comprehensive solution for managing events and ticket reservations. The project was designed to solve high-concurrency challenges in ticket sales by leveraging a **hybrid database approach**.

The core logic resides in a **Python API** that handles business rules, while a native **Swift (iOS)** application serves as the user interface.

### 🚀 Key Highlights for Engineers
* **Hybrid Database Architecture:** Utilizes **SQL** (MySQL/PostgreSQL) for transactional data integrity (orders, users) and **NoSQL** (Redis/MongoDB) for high-speed caching and session management.
* **RESTful API:** Built with **FastAPI** for high performance and automatic documentation.
* **Scalable Design:** Structured to handle peak loads during ticket releases.

---

## 🛠️ Tech Stack

| Component | Technology | Usage |
| :--- | :--- | :--- |
| **Backend** | Python, FastAPI | Core API and Business Logic |
| **Database (Relational)** | MySQL / PostgreSQL | User data, Transactions, and Inventory |
| **Database (NoSQL)** | Redis / MongoDB | Caching, Session Management, temporary holds |
| **Mobile Client** | Swift (iOS) | Native User Interface |
| **Tools** | Docker, Git | Containerization and Version Control |

---

## ⚙️ Architecture & Design

The system is built around the **Command Query Responsibility Segregation (CQRS)** concept basics:

1.  **Reads (High Performance):** Event listings and availability checks are cached in **Redis** to reduce load on the main database.
2.  **Writes (Consistency):** Ticket purchases and financial transactions are ACID-compliant, processed directly in **MySQL**.
3.  **Validation:** The Python backend sanitizes all inputs to prevent injection attacks and ensure logical consistency (e.g., no double booking).

---

## ⚡ Getting Started

Follow these steps to run the backend locally.

### Prerequisites
* Python 3.9+
* MySQL/PostgreSQL instance
* Redis instance

### Installation

1.  **Clone the repository**
    ```bash
    git clone [https://github.com/Andre-Atlas/TicketHub.git](https://github.com/Andre-Atlas/TicketHub.git)
    cd TicketHub
    ```

2.  **Create a virtual environment**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows use: venv\Scripts\activate
    ```

3.  **Install dependencies**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Configure Environment Variables**
    Create a `.env` file in the root directory:
    ```env
    DATABASE_URL=mysql+pymysql://user:password@localhost/tickethub
    REDIS_URL=redis://localhost:6379/0
    SECRET_KEY=your_secret_key --obviously we wouldn't expose ours lol
    ```

5.  **Run the Server**
    ```bash
    uvicorn main:app --reload
    ```

The API will be available at `http://127.0.0.1:8000`.
You can access the interactive documentation at `http://127.0.0.1:8000/docs`.

---

## 📱 Mobile App (iOS)

The frontend is a native iOS application built with Swift. To run it:
1.  Open the `ios-client` folder.
2.  Open `TicketHub.xcodeproj` in Xcode.
3.  Ensure the Backend is running.
4.  Build and run on the Simulator.

---

## 🤝 Contributing

Contributions are welcome! Please follow these steps:
1.  Fork the project.
2.  Create your Feature Branch (`git checkout -b feature/AmazingFeature`).
3.  Commit your changes (`git commit -m 'Add some AmazingFeature'`).
4.  Push to the Branch (`git push origin feature/AmazingFeature`).
5.  Open a Pull Request.

---

## 📄 License

Distributed under the MIT License. See `LICENSE` for more information.

---

<div align="center">
  <sub>Built with 💀 sheer power by <a href="https://github.com/Andre-Atlas">André Acioli</a></sub>
</div>
