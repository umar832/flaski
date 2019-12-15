from flask import render_template, Flask, Response, request, url_for, redirect, session
from app import app
from app.model import InputForm
from werkzeug.utils import secure_filename
import secrets
from flask_session import Session
import redis


import os
import io
import sys
import random

import matplotlib
matplotlib.use('agg')
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.backends.backend_svg import FigureCanvasSVG
from matplotlib.figure import Figure
import matplotlib.pyplot as plt
import mpld3

import pandas as pd

import base64

app.config['SESSION_TYPE'] = 'redis'
app.config['SESSION_REDIS'] = redis.from_url('redis://:REDIS_PASSWORD@127.0.0.1:6379/0')
app.config.from_object(__name__)

sess = Session()
sess.init_app(app)

session_token=secrets.token_urlsafe(16)
app.config["SECRET_KEY"] = session_token

ALLOWED_EXTENSIONS=["xlsx","tsv","csv"]
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
           
def make_figure(df,pa):
    x=df[pa["xvals"]].tolist()
    y=df[pa["yvals"]].tolist()

    # MAIN FIGURE
    fig = Figure()
    plt.scatter(x, y, marker=pa["marker"])
    plt.title(pa['title'], fontsize=int(pa["titles"]))

    return fig

@app.route('/', methods=['GET', 'POST'])
@app.route('/index', methods=['GET', 'POST'])
def index():
    """ 
    renders the plot on the fly.
    https://gist.github.com/illume/1f19a2cf9f26425b1761b63d9506331f
    """

    form = InputForm(request.form)

    if request.method == 'POST':

        # READ INPUT FILE
        inputfile = request.files["inputfile"]
        filename = secure_filename(inputfile.filename)
        fileread = inputfile.read()

        # SELECTION LISTS DO NOT GET UPDATED 
        lists={"xcols":"xvals","ycols":"yvals","markers":"marker",\
            "title_size":"titles"}

        # USER INPUT GETS UPDATED TO THE LATEST INPUT
        # WITH THE EXCEPTION OF SELECTION LISTS
        plot_arguments = session["plot_arguments"]
        for a in list(plot_arguments.keys()):
            if ( a in list(request.form.keys()) ) & ( a not in list(lists.keys()) ):
                plot_arguments[a]=request.form[a]

        # VALUES SELECTED FROM SELECTION LISTS 
        # GET UPDATED TO THE LATEST CHOICE
        for k in list(lists.keys()):
            if k in list(request.form.keys()):
                plot_arguments[lists[k]]=request.form[k]

        # UPDATE SESSION VALUES
        session["plot_arguments"]=plot_arguments
        
        # IF THE CURRENT FILE IS DIFERENT FROM 
        # THE FILE CURRENTLY IN MEMORY FOR THIS SESSION
        # THAN UPDATE THE SESSION FILE
        if session["fileread"] != fileread and \
            filename != "" and \
            filename != "Select file..":
            if allowed_file(inputfile.filename):
                session["fileread"]=fileread
                session["filename"]=filename
                extension=filename.rsplit('.', 1)[1].lower()
                if extension == "xlsx":
                    filestream=io.BytesIO(fileread)
                    df=pd.read_excel(filestream)
                elif extension == "csv":
                    df=pd.read_csv(fileread)
                elif extension == "tsv":
                    df=pd.read_csv(fileread,sep="\t")
                
                session["df"]=df.to_json()
                
                cols=df.columns.tolist()

                # IF THE USER HAS NOT YET CHOOSEN X AND Y VALUES THAN PLEASE SELECT
                if (session["plot_arguments"]["xvals"] not in cols) & (session["plot_arguments"]["yvals"] not in cols):

                    session["plot_arguments"]["xcols"]=cols
                    session["plot_arguments"]["xvals"]=cols[0]

                    session["plot_arguments"]["ycols"]=cols
                    session["plot_arguments"]["yvals"]=cols[1]
                
                    sometext="Please select which values should map to the x and y axes."
                    plot_arguments=session["plot_arguments"]
                    return render_template('index.html', form=form, filename=filename, sometext=sometext, **plot_arguments)
                
            else:
                # IF UPLOADED FILE DOES NOT CONTAIN A VALIDA EXTENSION PLEASE UPDATE
                error_message="You can can only upload files with the following extensions: 'xlsx', 'tsv', 'csv'. Please make sure the file '%s' \
                has the correct format and respective extension and try uploadling it again." %filename
                return render_template('index.html', form=form, filename="Select file..", error_message=error_message, **plot_arguments)
        
        # READ INPUT DATA FROM SESSION JSON
        df=pd.read_json(session["df"])

        # CALL FIGURE FUNCTION
        fig=make_figure(df,plot_arguments)

        # TRANSFORM FIGURE TO BYTES AND BASE64 STRING
        figfile = io.BytesIO()
        plt.savefig(figfile, format='png')
        plt.close()
        figfile.seek(0)  # rewind to beginning of file
        figure_url = base64.b64encode(figfile.getvalue()).decode('utf-8')

        # MAKE SURE WE HAVE THE LATEST ARGUMENTS FOR THIS SESSION
        filename=session["filename"]
        plot_arguments=session["plot_arguments"]
        return render_template('index.html', form=form, figure_url=figure_url, filename=filename, **plot_arguments)

    else:
        #sometext="get"

        # INITIATE SESSION
        session["filename"]="Select file.."
        session["fileread"]=None

        # DEFAULT ARGUMENTS
        # MARKER: https://matplotlib.org/3.1.1/api/markers_api.html
        plot_arguments={
            "title":'plot title',\
            "title_size":list(range(101))
            "titles":20
            "xcols":[],\
            "xvals":None,\
            "ycols":[],\
            "yvals":None,\
            "markers":[".",",","o","v","^","<",">",\
                "1","2","3","4","8",\
                "s","p","*","h","H","+","x",\
                "X","D","d","|","_"],\
            "marker":"."
        }
        session["plot_arguments"]=plot_arguments

        return render_template('index.html', form=form, filename=session["filename"], **plot_arguments)