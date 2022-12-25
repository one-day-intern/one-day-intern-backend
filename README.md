# One Day Intern 
![One Day Intern Logo](https://i.ibb.co/CzmHtCB/image.png)

**One Day Intern** is an open-source project that aims in making fairer and more practical assessments. 

We aim to provide means for:

-   Assessors to create an assessment environment that can emulate a day-to-day activity of a specific job position.
-   Assessors to identify, showcase, and differentiate which candidates have better practical and soft-skills abilities for their job/job position.
-   Assessee to gauge their day-to-day future work experience and provide a more natural and sincere performance than the ones performed in an isolated assessment environment.

## Frustrations that lead us to the creation of this project 😤
-   Some companies still use multiple external mediums for their assessment process. This situation becomes a hassle for HR and assessor personnels to manage, monitor, and guide the progress of their assesses throughout the assessment.
-   Some assessments are still performed separately and isolated from each other. These kinds of assessments are still incapable of mimicking the real-life work experience.

## Tables of Content 📃

### Getting started 💻
-   Server-side setup
-   Client-side setup
### Release Notes 📝
-   0.0.1 - Hello World Update
-   0.1.0 - The first pieces of the puzzle are here! 🥳
-   0.2.0 - Added tools, attempts, and grading 🤓

## Getting Started 🏃‍♂️🏃‍♀️
To start the project locally, please follow the steps below.

### Server-side setup 🛠

The server-side application runs on top of [Django](https://docs.djangoproject.com/en/4.1/) and [Django Rest Framework](https://www.django-rest-framework.org/). Hence, you will need to have python to be installed on your machine. 
Please follow these [installation steps](https://www.python.org/downloads/) to set up python on your machine. 

To ease the development process and to avoid hassle in production, you may also want to install python environment libraries. We use python _pipenv_ for this project.

Note that this project requires a Postgresql database to be installed in your local machine. 

If you do not have a local postgres instance in your machine, please follow these [installation steps](https://www.postgresqltutorial.com/postgresql-getting-started/install-postgresql/).

If you do not have a local postgres database in your machine, please follow these [steps](https://www.postgresql.org/docs/current/sql-createdatabase.html).

Once your local machine is set, you can start by following the steps below.

1.  First, clone the server-side repository.
    ```sh
    git clone https://github.com/one-day-intern/one-day-intern-backend.git
    ```

2.  After a successful repo-clone, you must install the dependencies to your local machine by using the following commands. 
    ```sh
    python -m pipenv shell
    cd one-day-intern-backend
    python -r requirements.txt
    ```

3.  Now, you need to set up the ```DATABASE_URL``` environment variable required to run the project. The ```DATABASE_URL``` has the following format ```postgres://{username}:{password}@{host}:{port}/{name}```.

	  Your ```DATABASE_URL``` should look something like this. ```postgres://postgres:postgres@localhost:5432/my_database```

	  You may do this by adding environment variables directly through the ```CLI (Command Line Interface)``` or through a ```.env``` file.
    
	To add the environment variables through the windows CMD, type the following command in your CLI.
	```sh
    export DATABASE_URL = <your_database_url>
	```
    
    For example,
    ```sh
    export DATABASE_URL = postgres://postgres:postgres@localhost:5432/my_database
	```
    
	To add the environment variables through the mac or linux CLI, type the following command in your CLI.
	```sh
	set DATABASE_URL = <your_database_url>
	```
    
    For example,
    ```sh
    set DATABASE_URL = postgres://postgres:postgres@localhost:5432/my_database
	```    
	
	To add the environment variable through the ```.env``` file, you may create a ```.env``` file in the root project directory and add the following line 	modified with your database credentials.
	```sh
	DATABASE_URL = <your_database_url>
	```
	For example,
	```sh
    DATABASE_URL = postgres://postgres:postgres@localhost:5432/my_database
	```

4.  If this is your first time running the application, perform the database migration as follows.
	```sh
    python manage.py migrate
    ```

5.  Finally, you can run the development server.
	```sh
    python manage.py runserver
    ```

	Now, you can open ```http://localhost:8000``` to see the application in the browser.

The application also comes with pre-configured test cases. To run the test locally, you can run ```python manage.py test``` 

### Client-side setup 🎨🖌
The client-side codebase consists of two separate repositories: ```odi-assessee-fe``` and ```odi-assessor-fe```, which handles the assessee and assessor dashboards, respectively.

1.  First, clone the repository you wish to contribute:

	The following is used to clone the assessee frontend:
	```sh
    git clone https://github.com/one-day-intern/odi-assessee-fe.git
    ```
	The following is used to clone the assessor frontend:
	```sh
    git clone https://github.com/one-day-intern/odi-assessor-fe.git
    ```

2.  Note that this project is configured using ```npm```. If ```npm``` is not configured on your machine, you can download node.js from the following [website](https://nodejs.org/en/), which comes bundled with ```npm```. 

	The steps for ```yarn``` users will be further specified below.

3.  After configuring ```npm``` in your machine, you can initialize the project by installing the dependencies as follows:
    ```sh
    npm i
    ```

	However, for those using ```yarn```, you can initialize the project by installing the dependencies as follows:
    ```sh
    yarn install
	```

4.  You also need to configure the ```BACKEND_URL``` for your Next.js application, which will most likely be ```http://localhost:XXXX``` (where you host our [cloned backend](https://github.com/one-day-intern/one-day-intern-backend)). 
	
    To configure the environment variables, you need to create a ```.env.local``` file which contains the following value:
	```js
	NEXT_PUBLIC_BACKEND_URL = <backend_url>
	```

	To access the following the backend URL on your browser-side code, you can use ```process.env.NEXT_PUBLIC_BACKEND_URL```.

	For those who prefer to add the variable to the next.config.js, you are able to add the following:
    ```js
    module.exports = {
      env: {
          ……,
          NEXT_PUBLIC_BACKEND_URL: <backend_url>,
        },
      }
    ```

5.  Both assessee and assessor applications are initialized using [Next.js](https://nextjs.org/docs). The development server in your local machine can be started as follows:

    ```sh
    npm run dev
    ```
    or 
	```sh
    yarn dev
	```
    
6.  You can open ```http://localhost:3000/``` to see the application in the browser. 

	(Note that if you were to run both applications simultaneously, one application may be run on ```http://localhost:3001/```)

Both applications also come pre-configured with cypress as the testing suite. To test the app locally you can run
```npx cypress open```
to test the app on your browser of choice.

## Release Notes 0.0.1 - Hello World Update 👋
Finish configuration of server-side and client-side repositories.

## Release Notes 0.1.0 - The first pieces of the puzzle are here! 🥳

### New Features
#### General
1. You can now either register and login as a `Company`, `Assessor`, 
   or an `Assessee` straight from the website

#### Companies and Assessors
1. Assessors can invite other employees to become `Assessors` by sending them a one time code
2. Assessors will receive an email containing a one time code to register

#### Test modules
1. Companies and Assessors can create `Assignments` and specify what type of
   file that needs be uploaded

#### Assessment Event
1. Assessors can create new Assessment Events
2. Assessors can assign other Assessors to an Assessment Event
3. Assessors can view Assessment Events that they're apart of
4. Assessors can see the Assessees that they're currently assessing

#### Video conference
1. Assessors can create video conferences
2. Assessors and Assessees can join video conferences

#### Assessees
1. Assessees can view their active assessment events
2. Assessees can access their assessment event desktops
3. Assessees can receive notifications from their desktop when they have a new assessment task


## Release Notes 0.2.0 - Added tools, attempts, and grading 🤓

### New Features
#### General
1. You can now either register and login as a `Company`, `Assessor`, 
   or an `Assessee` using Google Login

#### Assessor
1. Assessors can view the progress of the Assessees they are in charge of
2. Assessors can track the scores of every Assessee they are in charge of

#### Test modules
1. Companies and Assessors can create a fully customizable `Interactive Quiz`, including the number
   of questions, the type of question, points of each question and the answer key
2. Companies and Assessors can create `Response Tests` and specify the subject and prompt of the test

#### Test Flows
1. Companies and Assessors can create a fully customizable `Test Flow`, by selecting the Assessment 
   Tools used and the order and when they are published
2. Test Flows are assigned to Assessment Events

#### Assessment Attempts 
1. Assessees can now attempt their assigned assessments
   1. They can upload and reupload files for `Assignments`
   2. They can submit answers for `Interactive Quizzes`
   3. They can send a response back for `Response Tests`
2. Each assessment is set with a deadline, so they can only be done/accesses based on the deadline 
   constraint

#### Grading 
1. Assessors can now grade their Assessees attempts
   1. They can download files for `Assignments` and set their grade
   2. They can manually grade each answer for each question of an `Interactive Quizzes`
   3. They can manually grade `Response Tests`

#### Video Conference
1. Each pair of Assessors and Assessees are automatically assigned a video conference room
2. The Assessor acts as the host of the video conference room, which gives them full control of the room
3. Assessees can receive scheduled announcements for video conferences