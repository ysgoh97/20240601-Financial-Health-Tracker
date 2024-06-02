from flask import Flask, render_template, request, redirect, url_for, Markup
import os
import sqlite3
from pydrive.auth import GoogleAuth, ServiceAccountCredentials
from pydrive.drive import GoogleDrive
import datetime, pytz, time
from werkzeug.utils import secure_filename
import json
import google.generativeai as palm
import replicate
#from diffusers import StableDiffusionPipeline
#import torch
import matplotlib.pyplot as plt

flag = 1
name = ""
username = ""

makersuite_api = os.getenv("MAKERSUITE_API_TOKEN")
palm.configure(api_key=makersuite_api)
#os.environ["REPLICATE_API_TOKEN"] = ""

google_key = '/etc/secrets/client_secrets.json'
scope = ['https://www.googleapis.com/auth/drive']
gauth = GoogleAuth()
gauth.credentials = ServiceAccountCredentials.from_json_keyfile_name(google_key, scope)
drive = GoogleDrive(gauth)

app = Flask(__name__)
app.config["GENERATED_FOLDER"] = "static/generated"
app.config["SAMPLE_FOLDER"] = "static/sample"
app.config["UPLOAD_FOLDER"] = "static/uploads"

if not os.path.exists("static"):
    os.mkdir("static")
if not os.path.exists("static/generated"):
    os.mkdir("static/generated")
if not os.path.exists("static/sample"):
    os.mkdir("static/sample")
if not os.path.exists("static/uploads"):
    os.mkdir("static/uploads")


##############
### START ###
#############
@app.route("/",methods=["GET","POST"])
def index():
    conn = sqlite3.connect("log.db")
    c = conn.cursor()
    # c.execute("DROP TABLE IF EXISTS user")
    c.execute("CREATE TABLE IF NOT EXISTS user (username TEXT, name TEXT, email TEXT, password TEXT)")
    # c.execute("DROP TABLE IF EXISTS invoice")
    c.execute("CREATE TABLE IF NOT EXISTS invoice (username TEXT, time TIMESTAMP, invoice TEXT)")
    c.close()
    conn.close()
    return(render_template("index.html"))


######################
### LOGIN / SIGNUP ###
######################
@app.route("/login_fail",methods=["GET","POST"])
def login_fail():
    global flag, username, name
    if flag == 1:
        username = request.form.get("username")
        password = request.form.get("password")
        conn = sqlite3.connect("log.db")
        c = conn.cursor()
        c.execute("SELECT * FROM user WHERE username = ?", (username,))
        existing_user = c.fetchone()

        if not existing_user:
            error_message = "The username you entered does not exist."
            c.close()
            conn.close()
            return(render_template("login/login_fail.html", error_message=error_message))
            
        else:
            c.execute("SELECT password FROM user WHERE username = ?", (username,))
            password_row = c.fetchone()
            password_db = password_row[0]
            if password != password_db:
                error_message = "The password you entered is incorrect."
                c.close()
                conn.close()
                return(render_template("login/login_fail.html", error_message=error_message))

            else:
                c.execute("SELECT name FROM user WHERE username = ?", (username,))
                name_row = c.fetchone()
                name = name_row[0]
                flag = 0
                return(redirect(url_for("main")))

@app.route("/signup",methods=["GET","POST"])
def signup():
    return(render_template("login/signup.html"))

@app.route("/signup_message",methods=["GET","POST"])
def signup_message():
    name = request.form.get("name")
    username = request.form.get("username")
    email = request.form.get("email")
    password = request.form.get("password")
    password_cfm = request.form.get("password_cfm")

    conn = sqlite3.connect("log.db")
    c = conn.cursor()
    c.execute("SELECT * FROM user WHERE username = ?", (username,))
    existing_user = c.fetchone()
    
    if existing_user:
        error_message = "Username already exists."
        c.close()
        conn.close()
        return(render_template("login/signup_message.html", error_message=error_message))
        
    elif password != password_cfm:
        error_message = "Passwords do not match."
        c.close()
        conn.close()
        return(render_template("login/signup_message.html", error_message=error_message))
        
    else:
        signup_success = True
        c.execute("INSERT INTO user (username, name, email, password) VALUES(?,?,?,?)", 
                  (username, name, email, password))
        conn.commit()
        c.close()
        conn.close()
        return(render_template("login/signup_message.html", signup_success=signup_success))


############
### MAIN ###
############
@app.route("/main",methods=["GET","POST"])
def main():
    global flag, username, name
    if flag == 1:
        flag = 0
    return(render_template("main.html", name=name, username=username))


####################
### SCAN INVOICE ###
####################
@app.route("/scan_invoice",methods=["GET","POST"])
def scan_invoice():
    global username
    return(render_template("scan_invoice/scan_invoice.html", username=username))

@app.route("/display_invoice", methods=["GET", "POST"])
def display_invoice():
    global username, invoice_res
    username = request.form.get('username')
    file = request.files["file"]
    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    file.save(filepath)
    
    ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}
    def allowed_file(filename):
        return "." in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
    if not file or not allowed_file(file.filename):
        error_message = "Invalid file type. Allowed types: " + ", ".join(ALLOWED_EXTENSIONS)
        return render_template("scan_invoice/display_invoice.html", error_message=error_message)

    MAX_FILE_SIZE = 1 * 1024 * 1024  # 1 MB
    filesize = os.stat(filepath).st_size
    if filesize > MAX_FILE_SIZE:
        error_message = f"File size exceeds limit of {MAX_FILE_SIZE / 1024 / 1024} MB"
        return render_template("scan_invoice/display_invoice.html", error_message=error_message)

    upload_success = True
    image_url = url_for("static", filename=f"uploads/{filename}")
    start_time = time.time()
    try:
        folder_id = "1jndF65ntjku05ZlF5AVjeIBcieYFO8gF"
        file = drive.CreateFile({'parents': [{"id": folder_id}], 'title': filepath.split('/')[-1]})
        file.SetContentFile(filepath)
        file.Upload()
        file.InsertPermission({
            'type': 'anyone',
            'value': 'anyone',
            'role': 'reader'
            })
        gdrive_url = file['webContentLink'].split("&export=download")[0]
        r = replicate.run(
           "sulthonmb/ocr-receipt:7d2b5300247f1e85742ebd824a693c55fe4e4f6d50caaccb1265834f399754d6",
            input={"image": gdrive_url}
        )
        file.Delete()
        invoice_res = json.loads(r)
    except:
        image_url = url_for("static", filename="sample/invoice.jpg")
        invoice_res = {'menu': [{'nm': 'Tung Lok Curry Fish Head @38.00', 'cnt': '1 x', 'price': '38.00'},
                                {'nm': 'Crispy Fish Skin with Salted Egg Yolk @14.00', 'cnt': '1 x', 'price': '14.00'},
                                {'nm': 'Crispy Eggplant with Pork Floss @14.00', 'cnt': '1 x', 'price': '14.00'},
                                {'nm': 'Asparagus @20.00', 'cnt': '1 x', 'price': '20.00'},
                                {'nm': 'TungLok X.O. Rice Dumpling Bundle @49.20', 'cnt': '2 x', 'price': '98.40'},
                                {'nm': 'Oat Rice Dumpling with Mushrooms Bundle @46.80', 'cnt': '2 x', 'price': '46.80'}],
                       'sub_total': {'subtotal_price': '231.20', 'service_price': '0.00', 'tax_price': '18.02', 'etc': '-31.00'},
                       'total': {'total_price': '218.20'}}

    end_time = time.time()
    time_taken = end_time - start_time
    h = time_taken // 3600
    m = (time_taken % 3600) // 60
    s = time_taken % 60
    print(f"Time taken: {int(h)} h, {int(m)} min, and {s:.2f} s")
    return render_template('scan_invoice/display_invoice.html', 
                           username=username, 
                           upload_success=upload_success, 
                           image_url=image_url, 
                           invoice_res=invoice_res)

@app.route("/add_invoice",methods=["GET","POST"])
def add_invoice():
    global username, invoice_res
    username = request.form.get("username")
    tz = pytz.timezone('Asia/Singapore')
    current_time = datetime.datetime.now(tz)
    invoice_res = request.form.get("invoice_res")
    
    conn = sqlite3.connect("log.db")
    c = conn.cursor()
    c.execute("INSERT INTO invoice (username, time, invoice) VALUES(?,?,?)", 
                  (username, current_time, invoice_res))
    conn.commit()
    c.close()
    conn.close()
    return(render_template("scan_invoice/add_invoice.html", username=username, invoice_res=invoice_res))


############################
### SHOW SCANNED INVOICE ###
############################
@app.route("/show_invoice",methods=["GET","POST"])
def show_invoice():
    global username
    username = request.form.get('username')
    
    conn = sqlite3.connect('log.db')
    c = conn.cursor()
    c.execute("SELECT * FROM invoice WHERE username = ? ORDER BY time DESC;", (username,))
    r = c.fetchall()
    c.close()
    conn.close()

    table_data = []
    row_id = 0
    for row in r:
        _, time, invoice_str = row
        invoice_data = eval(invoice_str)['menu']
        total_price = list(eval(invoice_str)['total'].values())[0]
        item = ""
        for i in invoice_data:
            item += f"{i['cnt']} {i['nm']} <br>"
        row_id += 1
        table_data.append((row_id, time, Markup(item), total_price))
    table_data = table_data
    return(render_template("show_invoice/show_invoice.html", username=username, table_data=table_data))


######################
### DELETE INVOICE ###
######################
@app.route("/delete_invoice",methods=["GET","POST"])
def delete_invoice():
    global username
    username = request.form.get("username")
    
    conn = sqlite3.connect("log.db")
    c = conn.cursor()
    c.execute("SELECT * FROM invoice WHERE username = ? ORDER BY time DESC;", (username,))
    r = c.fetchall()
    c.close()
    conn.close()

    table_data = []
    row_id = 0
    for row in r:
        _, time, invoice_str = row
        invoice_data = eval(invoice_str)['menu']
        total_price = list(eval(invoice_str)['total'].values())[0]
        item = ""
        for i in invoice_data:
            item += f"{i['cnt']} {i['nm']} <br>"
        row_id += 1
        table_data.append((row_id, time, Markup(item), total_price))
    table_data = table_data
    return(render_template("delete_invoice/delete_invoice.html", username=username, table_data=table_data))

@app.route("/delete_invoice_cfm",methods=["GET","POST"])
def delete_invoice_cfm():
    global username
    username = request.form.get("username")
    del_time = request.form.get("del_time")
    del_time = datetime.datetime.strptime(del_time, '%Y-%m-%d %H:%M:%S.%f')

    conn = sqlite3.connect("log.db")
    c = conn.cursor()
    c.execute("DELETE FROM invoice WHERE username = ? AND time = ?", (username, del_time))
    conn.commit()
    
    c.execute("SELECT * FROM invoice WHERE username = ? ORDER BY time DESC;", (username,))
    r = c.fetchall()
    c.close()
    conn.close()

    table_data = []
    row_id = 0
    for row in r:
        _, time, invoice_str = row
        invoice_data = eval(invoice_str)['menu']
        total_price = list(eval(invoice_str)['total'].values())[0]
        item = ""
        for i in invoice_data:
            item += f"{i['cnt']} {i['nm']} <br>"
        row_id += 1
        table_data.append((row_id, time, Markup(item), total_price))
    table_data = table_data
    return(render_template("delete_invoice/delete_invoice_cfm.html", username=username, table_data=table_data))



########################
### FINANCIAL HEALTH ###
########################
@app.route("/fin_health",methods=["GET","POST"])
def fin_health():
    global username
    return(render_template("fin_health/fin_health.html", username=username))

@app.route("/fin_result",methods=["GET","POST"])
def fin_result():
    global username
    username = request.form.get('username')
    income = request.form.get("income")
    expense = request.form.get("expense")
    asset = request.form.get("asset")
    debt = request.form.get("debt")

    conn = sqlite3.connect("log.db")
    c = conn.cursor()
    c.execute("SELECT * FROM invoice WHERE username = ?", (username,))
    r = ""
    for row in c:
      r+= str(row) + "<br><br>"
    c.close()
    conn.close()

    def format_response(text):
        lines = text.splitlines()
        formatted_lines = []
        for line in lines:
            if line.startswith("*"):
                formatted_lines.append("<br><br>" + line)
            else:
                formatted_lines.append(line)
        return Markup("\n".join(formatted_lines))

    prompt = f"monthly income = {income}, monthly expense = {expense}, total asset = {asset}, total debt = {debt}. "
    prompt += f"In addition to the monthly expense, I also have expenses logged in the database as follows: {r}. "
    prompt += "How is my financial health? "
    
    prompt2 = f"monthly income = {income}, monthly expense = {expense}, total asset = {asset}, total debt = {debt}. "
    prompt2 += f"In addition to the monthly expense, I also have expenses logged in the database as follows: {r}. "
    prompt2 += "In a new paragraph, list 5 credits card in Singapore that are suitable for me. "
    prompt2 += "Use * to start a list."

    start_time = time.time()
    model = {"model": "models/chat-bison-001"}
    r = palm.chat(**model, messages=prompt)
    r2 = palm.chat(**model, messages=prompt2)
    fin_res = format_response(r.last)
    fin_res2 = format_response(r2.last)
    
    def plot_bars(income, expense, asset, debt):
        income, expense, asset, debt = float(income), float(expense), float(asset), float(debt)
        
        fig = plt.figure(figsize=(10, 6))

        # Income and Expense
        plt.subplot(1, 2, 1)
        plt.title("Monthly Income vs. Monthly Expense")
        plt.bar(["Income", "Expense"], [income, expense], color=['green', 'red'])
        plt.ylabel("Amount ($)")
        plt.ylim([0, max(income, expense)*1.05])
        
        # Total Asset vs. Total Debt
        plt.subplot(1, 2, 2)
        plt.title("Total Asset vs. Total Debt")
        plt.bar(["Asset", "Debt"], [asset, debt], color=['green', 'red'])
        plt.ylabel("Amount ($)")
        plt.ylim([0, max(asset, debt)*1.05])
        
        plt.tight_layout()
        fig.savefig(os.path.join(app.config["GENERATED_FOLDER"], "financial_charts.png"), bbox_inches="tight")
        plt.close(fig)
        charts = url_for("static", filename="generated/financial_charts.png")
        return charts
    charts = plot_bars(income, expense, asset, debt)

    end_time = time.time()
    time_taken = end_time - start_time
    h = time_taken // 3600
    m = (time_taken % 3600) // 60
    s = time_taken % 60
    print(f"Time taken: {int(h)} h, {int(m)} min, and {s:.2f} s")
    return(render_template("fin_health/fin_result.html", username=username, fin_res=fin_res, fin_res2=fin_res2, charts=charts))
    

###############################
### CREDIT CARD APPLICATION ###
###############################
@app.route("/card_app",methods=["GET","POST"])
def card_app():
    return(render_template("card_app/card_app.html"))

@app.route("/card_result",methods=["GET","POST"])
def card_result():
    card = request.form.get("card")
    design = request.form.get("design")
    prompt = f"{design} design printed on a credit card"
    start_time = time.time()
    try:
        r = replicate.run(
           "stability-ai/stable-diffusion:db21e45d3f7023abc2a46ee38a23973f6dce16bb082a930b0c49861f96d1e5bf",
            input={"prompt": prompt}
        )
        card_res = r[0]
    except:
        # There is not enough memory on free render account to run this model
        # try:
        #     pipeline = StableDiffusionPipeline.from_pretrained("runwayml/stable-diffusion-v1-5", 
        #                                                        torch_dtype=torch.float32)
        #     image = pipeline(prompt, nwum_images_per_prompt=1).images[0]
        #     image.save(os.path.join(app.config["GENERATED_FOLDER"], "card_design.png"))
        #     card_res = url_for("static", filename="generated/card_design.png")
        # except:
        design = "whale"
        card_res = url_for("static", filename="sample/card_design.jpeg")

    end_time = time.time()
    time_taken = end_time - start_time
    h = time_taken // 3600
    m = (time_taken % 3600) // 60
    s = time_taken % 60
    print(f"Time taken: {int(h)} h, {int(m)} min, and {s:.2f} s")
    return(render_template("card_app/card_result.html", card=card, design=design, card_res=card_res))

@app.route("/card_cfm",methods=["GET","POST"])
def card_cfm():
    return(render_template("card_app/card_cfm.html"))


######################
### DELETE ACCOUNT ###
######################
@app.route("/delete_acc",methods=["GET","POST"])
def delete_acc():
    global username
    return(render_template("delete_acc/delete_acc.html", username=username))
    
@app.route("/delete_acc_message",methods=["GET","POST"])
def delete_acc_message():
    global username
    username_in = request.form.get("username")
    password_in = request.form.get("password")

    conn = sqlite3.connect("log.db")
    c = conn.cursor()
    c.execute("SELECT * FROM user WHERE username = ?", (username,))
    existing_user = c.fetchone()

    if username_in != username:
        error_message = "The username you entered is incorrect."
        c.close()
        conn.close()
        return(render_template("delete_acc/delete_acc_message.html", error_message=error_message))

    c.execute("SELECT password FROM user WHERE username = ?", (username,))
    password_row = c.fetchone()
    password_db = password_row[0]
    if password_in != password_db:
        error_message = "The password you entered is incorrect."
        c.close()
        conn.close()
        return(render_template("delete_acc/delete_acc_message.html", error_message=error_message))

    else:
        delete_success = True
        c.execute("DELETE FROM user WHERE username = ?", (username,))
        c.execute("DELETE FROM invoice WHERE username = ?", (username,))
        conn.commit()
        c.close()
        conn.close()
        return(render_template("delete_acc/delete_acc_message.html", delete_success=delete_success))


############
### END ###
###########
@app.route("/end",methods=["GET","POST"])
def end():
    global flag, username, name
    flag = 1
    name = ""
    username = ""

    files = os.listdir(app.config["GENERATED_FOLDER"])
    if len(files) > 0:
        for file in files:
            os.remove(os.path.join(app.config["GENERATED_FOLDER"], file))
            
    files = os.listdir(app.config["UPLOAD_FOLDER"])
    if len(files) > 0:
        for file in files:
            os.remove(os.path.join(app.config["UPLOAD_FOLDER"], file))
    return(render_template("index.html"))


############
### lOG ###
###########
@app.route("/user_log",methods=["GET","POST"])
def user_log():
    conn = sqlite3.connect("log.db")
    c = conn.cursor()
    c.execute("SELECT * FROM user")
    r = ""
    for row in c:
      r+= str(row) + "<br><br>"
    r = Markup(r)
    c.close()
    conn.close()
    return(render_template("log/user_log.html", r=r))

@app.route("/user_deleteALL",methods=["GET","POST"])
def user_deleteALL():
    conn = sqlite3.connect("log.db")
    c = conn.cursor()
    c.execute("DELETE FROM user")
    conn.commit()
    c.close()
    conn.close()
    return(render_template("log/user_deleteALL.html"))

@app.route("/invoice_log",methods=["GET","POST"])
def invoice_log():
    conn = sqlite3.connect("log.db")
    c = conn.cursor()
    c.execute("SELECT * FROM invoice")
    r = ""
    for row in c:
      r+= str(row) + "<br><br>"
    r = Markup(r)
    c.close()
    conn.close()
    return(render_template("log/invoice_log.html", r=r))

@app.route("/invoice_deleteALL",methods=["GET","POST"])
def invoice_delete():
    conn = sqlite3.connect("log.db")
    c = conn.cursor()
    c.execute("DELETE FROM invoice")
    conn.commit()
    c.close()
    conn.close()
    return(render_template("log/invoice_deleteALL.html"))


############
### RUN ###
###########
if __name__ == "__main__":
    app.run()
