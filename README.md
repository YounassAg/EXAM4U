# Exam4U

Exam4U is a Django-based web application designed to facilitate the creation and management of exams. It provides a user-friendly interface for teachers to create exams, add questions, and manage exam settings.

## Features

- Create and manage exams with various settings.
- Add multiple types of questions, including Multiple Choice, Open Questions, and Short Answers.
- Dynamic form for adding questions and choices.
- User authentication and authorization.

## Installation

1. **Clone the repository:**

   ```bash
   git clone https://github.com/yourusername/exam4u.git
   cd exam4u
   ```

2. **Create a virtual environment:**

   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows use `venv\Scripts\activate`
   ```

3. **Install dependencies:**

   ```bash
   pip install -r requirements.txt
   ```

4. **Set up the database:**

   Ensure you have MySQL installed and running. Create a database and a user with the necessary permissions. Update the `DATABASES` setting in `exam4u/settings.py` with your database credentials:

   ```python
   DATABASES = {
       'default': {
           'ENGINE': 'django.db.backends.mysql',
           'NAME': 'your_database_name',
           'USER': 'your_database_user',
           'PASSWORD': 'your_database_password',
           'HOST': 'localhost',  # or your database host
           'PORT': '3306',       # or your database port
       }
   }
   ```

5. **Apply migrations:**

   ```bash
   python manage.py migrate
   ```

6. **Run the development server:**

   ```bash
   python manage.py runserver
   ```

7. **Access the application:**

   Open your web browser and go to `http://127.0.0.1:8000`.

## Usage

- Log in as a teacher to create and manage exams.
- Use the "Create Exam" page to set up a new exam, add questions, and configure settings.
- Manage existing exams through the dashboard.

## Contributing

Contributions are welcome! Please fork the repository and submit a pull request for any improvements or bug fixes.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
