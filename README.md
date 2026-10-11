# 🏋️‍♂️ Fitness & Progress Tracker Web App

A full-stack web application designed to log workout routines, standardize data entries, and visualize physical progression over time. 

This project demonstrates the integration of a Python backend with a relational database and data science libraries to solve a real-world data tracking problem.

## 🚀 Technologies Used
* **Backend:** Python, Flask
* **Database:** PostgreSQL, psycopg2
* **Data Analysis & Visualization:** Pandas, Matplotlib, Seaborn
* **Frontend:** HTML5, Bootstrap 5

## 💡 Key Features
* **Automated Data Cleaning:** Built-in dictionary mapping to standardize messy user inputs (e.g., standardizing "bench", "BENCH", and " bench press " into a clean "Bench Press" string).
* **Database Integration:** Securely stores workout logs (exercise name, weight, reps, and timestamp) in a PostgreSQL database with automated table generation.
* **Dynamic Visualization:** Automatically queries the database using Pandas and renders a progression trendline chart using Seaborn and Matplotlib on the web interface.

## 🛠️ How to Run Locally
1. Clone the repository:
   ```bash
   git clone [https://github.com/YOUR_USERNAME/fitness-tracker.git](https://github.com/YOUR_USERNAME/fitness-tracker.git)