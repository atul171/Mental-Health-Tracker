# Mental Health Tracker

## Overview

The Mental Health Tracker is a web-based application designed to help users monitor and understand their emotional well-being. It enables users to log daily moods, store personal reflections, and interact with an AI-powered assistant for insights and support.

The application is built using Flask for the backend, MongoDB Atlas for cloud-based data storage, and the Gemini API for AI-driven interactions. The frontend is developed using HTML, CSS, and JavaScript to provide a responsive and user-friendly interface.

---

## Objectives

* Provide a simple platform for users to track their daily mental state
* Enable secure storage and retrieval of user data
* Offer AI-generated responses for guidance and reflection
* Help users identify patterns in their emotional health over time

---

## Features

### Mood Tracking

Users can record their daily mood and associated notes. This data is stored and can be accessed later for review.

### AI-Based Interaction

The application integrates the Gemini API to provide contextual responses based on user input, helping users reflect on their thoughts.

### Cloud Database Integration

MongoDB Atlas is used to store user data securely and ensure availability across sessions.

### Web Interface

A clean and responsive interface built with HTML, CSS, and JavaScript ensures ease of use across devices.

---

## Technology Stack

**Backend**

* Python (Flask)

**Frontend**

* HTML
* CSS
* JavaScript

**Database**

* MongoDB Atlas

**API**

* Gemini API

**Version Control**

* Git and GitHub

---

## System Architecture

The application follows a client-server architecture:

* The frontend handles user interaction and sends requests to the backend
* The Flask backend processes requests, interacts with the database, and communicates with the Gemini API
* MongoDB Atlas stores user data such as mood logs and responses
* The Gemini API processes user input and generates AI-based replies

---

## Project Structure

```
project/
 ┣ static/
 ┃ ┣ css/
 ┃ ┣ js/
 ┣ templates/
 ┃ ┣ index.html
 ┣ app.py
 ┣ requirements.txt
 ┗ config/
```

---

## Installation and Setup

### Prerequisites

* Python 3.x installed
* MongoDB Atlas account
* Gemini API key

### Steps

1. Clone the repository:

```
git clone https://github.com/atul171/Mental-Health-Tracker.git
```

2. Navigate to the project directory:

```
cd Mental-Health-Tracker
```

3. Create a virtual environment:

```
python -m venv venv
```

4. Activate the virtual environment:

* Windows:

```
venv\Scripts\activate
```

* macOS/Linux:

```
source venv/bin/activate
```

5. Install dependencies:

```
pip install -r requirements.txt
```

---

## Configuration

Create a `.env` file in the root directory and include the following:

```
MONGO_URI=your_mongodb_atlas_connection_string
GEMINI_API_KEY=your_gemini_api_key
SECRET_KEY=your_secret_key
```

Ensure that environment variables are securely managed and not exposed in version control.

---

## Running the Application

Start the Flask server using:

```
python app.py
```

Access the application in a web browser at:

```
http://127.0.0.1:5000/
```

---

## Future Enhancements

* Implementation of user authentication and authorization
* Data visualization for mood trends and analytics
* Notification system for daily reminders
* Improved mobile responsiveness
* Dark mode support

---

## Limitations

* The application does not replace professional mental health services
* AI-generated responses may not always be contextually accurate
* Requires internet connectivity for database and API access

---

## Contribution Guidelines

Contributions are welcome. Fork the repository, create a feature branch, and submit a pull request with a clear description of changes.

---

## License

This project is open-source and can be distributed under the MIT License.

---

## Author

Atul Krishna
GitHub: https://github.com/atul171

---

## Disclaimer

This application is intended for self-monitoring and awareness purposes only. It is not a substitute for professional mental health advice, diagnosis, or treatment.
