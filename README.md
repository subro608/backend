
# House Hunt App - Backend

This is the backend repository for the **House Hunt App**, built using Django. This app allows users to create profiles, search for property listings, manage wishlists, and interact with listings. It is designed to facilitate easy setup and contribution for new developers.

## Table of Contents

-   [Tech Stack](#tech-stack)
-   [Getting Started](#getting-started)
    -   [Prerequisites](#prerequisites)
    -   [Installation](#installation)
    -   [Running the Server](#running-the-server)
-   [Contributing](#contributing)

## Tech Stack

-   **Language**: Python
-   **Framework**: Django
-   **Database**: PostgreSQL (default, but can be configured)
-   **Environment Management**: `venv` or `virtualenv`
-   **API Documentation**: Django REST Framework

## Getting Started

### Prerequisites

Make sure you have the following installed on your system:

-   Python 3.8+
-   `git`

### Installation

1.  **Clone the repository**:
    
    bash
    
    Copy code
    
    ``git clone https://github.com/cs-gy-6603-househunting/backend.git ``
    ``cd backend ``
    
2.  **Create a virtual environment**:
    
    
    `python3 -m venv venv` 
    
3.  **Activate the virtual environment**:
    
    -   On macOS/Linux:
        
        `source venv/bin/activate` 
        
    -   On Windows:
        
        `venv\Scripts\activate` 
        
4.  **Install dependencies**:
    
    `pip install -r requirements.txt`

### Running the Server

Start the Django development server:

`python manage.py runserver` 

The server will start on `http://127.0.0.1:8000/`.

### Running Tests

To run the tests, use:

`python manage.py test`


## Contributing

We welcome contributions to improve the House Hunt App! To contribute:

1.  **Fork the repository** and create your branch:
    
    `git checkout -b feature/your-feature-name` 
    
2.  **Make your changes** and **commit** them:
    
       `git commit -m "Add your commit message here"` 
    
3.  **Push to your forked repository**:
    
    
    `git push origin feature/your-feature-name` 
    
4.  **Create a pull request** against the `develop` branch of the original repository.
    

### Code Style Guidelines

-   Use **black** formatter regularly, especially before pushing your code to a branch.
-   Follow **PEP 8** for Python code style.
-   Use **docstrings** for methods and classes.
-   Ensure **tests** are written for new features or changes.
