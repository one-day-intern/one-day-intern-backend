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