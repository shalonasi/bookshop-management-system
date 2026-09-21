# Bookshop Management System

An offline bookshop management system built with Python, Flask and SQLite.

## Overview

The Bookshop Management System is a web-based application designed to help manage the daily operations of a bookshop. It provides an interface for managing products, categories, stock, sales, users and reports from a local computer.

The system is designed to work offline and uses SQLite for local data storage.

## Features

* Admin login and user management
* Product management
* Category management
* Stock management
* Stock movement history
* Sales recording
* Sales history and details
* Sales reports
* Low-stock monitoring
* Printable sales receipts
* Local SQLite database
* Offline operation

## Technologies Used

* Python
* Flask
* Flask-SQLAlchemy
* SQLite
* HTML
* CSS
* JavaScript
* ReportLab

## Project Structure

```text
bookshop_management/
├── app.py
├── create_admin.py
├── desktop.py
├── extensions.py
├── models/
├── static/
│   ├── css/
│   └── images/
├── templates/
├── .gitignore
└── README.md
```

## How to Run

### 1. Clone the repository

```bash
git clone https://github.com/shalonasi/bookshop-management-system.git
```

### 2. Open the project directory

```bash
cd bookshop-management-system
```

### 3. Create and activate a virtual environment

On Windows:

```powershell
python -m venv .venv
.venv\Scripts\activate
```

### 4. Install the required packages

```powershell
pip install flask flask-sqlalchemy reportlab
```

### 5. Run the application

```powershell
python app.py
```

Then open the local address shown in the terminal in your web browser.


## Project Purpose

The system was developed to provide a simple way of managing bookshop operations digitally, reducing reliance on manual records and making it easier to monitor products, stock and sales.

## Author

**Shalon Asi**

Computer Science Student

