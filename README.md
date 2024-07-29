# Description
This repository is a group assignment for the module "AI and Analytics in Finance, Credit and Related Risks (2024 Int12)", as part of NTU FlexiMasters in Business and Financial Analytics. The deployed web application can be found [here](https://two0240601-financial-health-tracker.onrender.com).

The objective of this project is to enhance financial services for a bank by developing a web application that utilises AI to automate invoice processing and provide personalised financial advisory services. 

The application addresses the following problems:
* Manual Data Entry: Manually entering invoice data and financial transactions can be tedious and prone to errors
* Lack of Personalised Financial Guidance: Many customers struggle to understand their financial health and make informed decisions
* Decision Paralysis in Credit Card Applications: Customers may be overwhelmed by the wide range of credit cards (or other financial products) to choose from, leading to stress and indecision

This application offers a unique solution by:
* Automating invoice data entry through AI-powered scanning, thus reducing manual processes and errors
* Using generative AI to offer personalised financial health assessments and credit card recommendations based on user-provided data
* Creating visually engaging experience with income/expense and asset/debt disparity charts
* Allowing users to design their own credit cards with generative AI, increasing user engagement and creating unique user experience
* Providing a user-friendly platform for managing invoices and financial information

The application is built with SQLite, Python, HTML, and Flask, and is deployed on Render. This initial project phase focuses on the following core functionalities:
* User account creation and login
* Invoice uploading, scanning, and extraction using OCR (Replicate)***
* User interface for displaying and deleting stored invoices
* Financial health assessment through user-provided data using LLM (PaLM)
* Visual representation of income/expense and asset/debt disparity highlighting the financial health status
* Personalised credit card recommendations using  LLM (PaLM) 
* Personalised credit card design using Stable Diffusion (Replicate)***

DISCLAIMER: As Replicate models are not free, the functionalities marked with *** will be replaced with dummy model outputs once the Replicate account used for deployment runs out of credit. 
