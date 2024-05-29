from flask import Flask, render_template, request, redirect, url_for, Markup
import os
import sqlite3
import datetime
from werkzeug.utils import secure_filename
import replicate
import google.generativeai as palm

flag = 1
name = ""
username = ""

makersuite_api = os.getenv("MAKERSUITE_API_TOKEN")
palm.configure(api_key=makersuite_api)

model = {"model": "models/chat-bison-001"}

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'static/uploads'
if not os.path.exists('static'):
    os.mkdir('static')
if not os.path.exists('static/uploads'):
    os.mkdir('static/uploads')

    
@app.route("/",methods=["GET","POST"])
def index():
    conn = sqlite3.connect('log.db')
    c = conn.cursor()
    # c.execute("DROP TABLE IF EXISTS user")
    c.execute("CREATE TABLE IF NOT EXISTS user (username TEXT, name TEXT, email TEXT, password TEXT)")
    # c.execute("DROP TABLE IF EXISTS invoice")
    c.execute("CREATE TABLE IF NOT EXISTS invoice (username TEXT, time TIMESTAMP, invoice TEXT)")
    c.close
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
        conn = sqlite3.connect('log.db')
        c = conn.cursor()
        c.execute("SELECT * FROM user WHERE username = ?", (username,))
        existing_user = c.fetchone()

        if not existing_user:
            error_message = "The username you entered does not exist."
            c.close
            conn.close()
            return(render_template("login/login_fail.html", error_message=error_message))
            
        else:
            c.execute("SELECT password FROM user WHERE username = ?", (username,))
            password_row = c.fetchone()
            password_db = password_row[0]
            if password != password_db:
                error_message = "The password you entered is incorrect."
                c.close
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

    conn = sqlite3.connect('log.db')
    c = conn.cursor()
    c.execute("SELECT * FROM user WHERE username = ?", (username,))
    existing_user = c.fetchone()
    
    if existing_user:
        error_message = "Username already exists."
        c.close
        conn.close()
        return(render_template("login/signup_message.html", error_message=error_message))
        
    elif password != password_cfm:
        error_message = "Passwords do not match."
        c.close
        conn.close()
        return(render_template("login/signup_message.html", error_message=error_message))
        
    else:
        signup_success = True
        c.execute("INSERT INTO user (username, name, email, password) VALUES(?,?,?,?)", 
                  (username, name, email, password))
        conn.commit()
        c.close
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

@app.route('/display_invoice', methods=['GET', 'POST'])
def display_invoice():
    global username, invoice_res
    username = request.form.get('username')
    file = request.files['file']
    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)
    
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
    def allowed_file(filename):
        return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
    if not file or not allowed_file(file.filename):
        error_message = 'Invalid file type. Allowed types: ' + ', '.join(ALLOWED_EXTENSIONS)
        return render_template('scan_invoice/display_invoice.html', error_message=error_message)

    MAX_FILE_SIZE = 1 * 1024 * 1024  # 1 MB
    filesize = os.stat(filepath).st_size
    if filesize > MAX_FILE_SIZE:
        error_message = f'File size exceeds limit of {MAX_FILE_SIZE / 1024 / 1024} MB'
        return render_template('scan_invoice/display_invoice.html', error_message=error_message)

    upload_success = True
    image_url = url_for('static', filename=f'uploads/{filename}')
    
    # r = replicate.run(
    #    "sulthonmb/ocr-receipt:7d2b5300247f1e85742ebd824a693c55fe4e4f6d50caaccb1265834f399754d6",
    #     input={"image": image_url}
    # )
    r = ['{"menu": [{"nm": "Nasi Campur Bali", "cnt": "1 x", "price": "75,000"}, {"nm": "Bbk Bengil Nasi", "cnt": "1 x", "price": "125,000"}],"sub_total": {"subtotal_price": "1,346,000", "service_price": "100,950", "tax_price": "144,695", "etc": "-45"}, "total": {"total_price": "1,591,600"}}']
    invoice_res = r[0]
    return render_template('scan_invoice/display_invoice.html', 
                           username=username, 
                           upload_success=upload_success, 
                           image_url=image_url, 
                           invoice_res=invoice_res)

@app.route("/add_invoice",methods=["GET","POST"])
def add_invoice():
    global username, invoice_res
    username = request.form.get('username')
    current_time = datetime.datetime.now()
    invoice_res = request.form.get('invoice_res')
    
    conn = sqlite3.connect('log.db')
    c = conn.cursor()
    c.execute("INSERT INTO invoice (username, time, invoice) VALUES(?,?,?)", 
                  (username, current_time, invoice_res))
    conn.commit()
    c.close
    conn.close()
    return(render_template("scan_invoice/add_invoice.html", username=username, invoice_res=invoice_res))


######################
### DELETE INVOICE ###
######################
@app.route("/delete_invoice",methods=["GET","POST"])
def delete_invoice():
    global username
    username = request.form.get('username')
    
    conn = sqlite3.connect('log.db')
    c = conn.cursor()
    c.execute("SELECT * FROM invoice WHERE username = ?", (username,))
    r = ""
    for row in c:
      r+= str(row) + "<br><br>"
    r = Markup(r)
    c.close
    conn.close()
    return(render_template("delete_invoice/delete_invoice.html", username=username, r=r))

@app.route("/delete_cfm",methods=["GET","POST"])
def delete_cfm():
    global username
    username = request.form.get('username')
    del_time = request.form.get('del_time')
    del_time = datetime.datetime.strptime(del_time, '%Y-%m-%d %H:%M:%S.%f')

    conn = sqlite3.connect('log.db')
    c = conn.cursor()
    c.execute("DELETE FROM invoice WHERE username = ? AND time = ?", (username, del_time))
    conn.commit()
    
    c.execute("SELECT * FROM invoice WHERE username = ?", (username,))
    r = ""
    for row in c:
      r+= str(row) + "<br><br>"
    r = Markup(r)
    c.close
    conn.close()
    return(render_template("delete_invoice/delete_cfm.html", username=username, r=r))



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

    conn = sqlite3.connect('log.db')
    c = conn.cursor()
    c.execute("SELECT * FROM invoice WHERE username = ?", (username,))
    r = ""
    for row in c:
      r+= str(row) + "<br><br>"
    c.close
    conn.close()

    prompt = f"monthly income = {income}, monthly expense = {expense}, total asset = {asset}, total debt = {debt}. "
    prompt += f"In addition to the monthly expense, I also have expenses logged in the database as follows: {r}. "
    prompt += "How is my financial health? "
    prompt += "In a new paragraph, list credits card in Singapore that are suitable for me. "
    
    r = palm.chat(**model, messages=prompt)
    fin_res = Markup(r.last)
    return(render_template("fin_health/fin_result.html", username=username, fin_res=fin_res))
    

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
    prompt = f"credit card with {design} design"
    # r = replicate.run(
    #    "stability-ai/stable-diffusion:db21e45d3f7023abc2a46ee38a23973f6dce16bb082a930b0c49861f96d1e5bf",
    #     input={"prompt": prompt}
    # )
    r = ["https://upload.wikimedia.org/wikipedia/commons/7/7f/Taylor_Swift_%286966830273%29.jpg?20141124081306"]
    card_res = r[0]
    return(render_template("card_app/card_result.html", card=card, design=design, card_res=card_res))

@app.route("/card_cfm",methods=["GET","POST"])
def card_cfm():
    return(render_template("card_app/card_cfm.html"))


############
### END ###
###########
@app.route("/end",methods=["GET","POST"])
def end():
    global flag, username, name
    flag = 1
    name = ""
    username = ""
    
    files = os.listdir(app.config['UPLOAD_FOLDER'])
    if len(files) > 0:
        for file in files:
            os.remove(os.path.join(app.config['UPLOAD_FOLDER'], file))
    return(render_template("index.html"))


############
### lOG ###
###########
@app.route("/user_log",methods=["GET","POST"])
def user_log():
    conn = sqlite3.connect('log.db')
    c = conn.cursor()
    c.execute("SELECT * FROM user")
    r = ""
    for row in c:
      r+= str(row) + "<br><br>"
    r = Markup(r)
    c.close
    conn.close()
    return(render_template("log/user_log.html", r=r))

@app.route("/user_delete",methods=["GET","POST"])
def user_delete():
    conn = sqlite3.connect('log.db')
    c = conn.cursor()
    c.execute("DELETE FROM user")
    conn.commit()
    c.close
    conn.close()
    return(render_template("log/user_delete.html"))

@app.route("/invoice_log",methods=["GET","POST"])
def invoice_log():
    conn = sqlite3.connect('log.db')
    c = conn.cursor()
    c.execute("SELECT * FROM invoice")
    r = ""
    for row in c:
      r+= str(row) + "<br><br>"
    r = Markup(r)
    c.close
    conn.close()
    return(render_template("log/invoice_log.html", r=r))

@app.route("/invoice_delete",methods=["GET","POST"])
def invoice_delete():
    conn = sqlite3.connect('log.db')
    c = conn.cursor()
    c.execute("DELETE FROM invoice")
    conn.commit()
    c.close
    conn.close()
    return(render_template("log/invoice_delete.html"))


############
### RUN ###
###########
if __name__ == "__main__":
    app.run()
