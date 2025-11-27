from flask import Flask
import google.oauth2.id_token
from flask import Flask, render_template, request ,redirect
from google.auth.transport import requests
import requests as req
from google.cloud import datastore, storage
import uuid
from datetime import datetime
import hashlib
from google.auth.transport import requests

app = Flask(__name__)

datastore_client = datastore.Client()
firebase_request_adapter = requests.Request()
client = storage.Client()
bucket = client.bucket('gallery.appspot.com')



def retrieveUserInfo(claims):
    entity_key = datastore_client.key('user_info', claims['email'])
    entity = datastore_client.get(entity_key)
    return entity
    
 
def createUserInfo(claims):
    entity_key = datastore_client.key('user_info', claims['email'])
    entity = datastore.Entity(key = entity_key)
    if 'name' in claims:
        name = claims['name']
    else:
        name = None 
    entity.update({
        'email': claims['email'],
         'user_id' : str(uuid.uuid4()),
    }) 
    datastore_client.put(entity)

def retrieveGalleries(user_info):
    query = datastore_client.query(kind='gallery_data')
    query.add_filter('user_id', '=', user_info['user_id'])
    result = list(query.fetch())
    return result

def getSingleGalleryInfo(token):
    entity_key = datastore_client.key('gallery_data', token)
    entity = datastore_client.get(entity_key)
    return entity

#conditions and supported formats 
file_types = {'png', 'jpg','jpeg'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in file_types

def getGalleryNameExistsOrNot(name, user_id):
    query = datastore_client.query(kind='gallery_data')
    query.add_filter('user_id', '=', user_id)
    query.add_filter('gallery_name', '=', name)
    result = list(query.fetch())
    if(len(result) > 0):
        return True
    else:
        return False


def getGalleryImages(user_id, gallery_id):
    query = datastore_client.query(kind='images_data')
    query.add_filter('user_id', '=', user_id['user_id'])
    query.add_filter('gallery_id', '=', gallery_id)
    result = list(query.fetch())
    return result

def sha1_method(image_data):
    sha1_hash = hashlib.sha1(image_data).hexdigest()
    return sha1_hash

def duplicate_images(images):
    duplicates = []
    hash_codes = {}
    image_urls = [image['image_url'] for image in images]
    for url in image_urls:
        image_data = req.get(url).content
        image_hash = sha1_method(image_data)
        if image_hash in hash_codes:
            duplicates.append(url)
            duplicates.append(hash_codes[image_hash])
        else:
            hash_codes[image_hash] = url
    return duplicates

def getTotalImagesOfUser(user_info):
    query = datastore_client.query(kind='images_data')
    query.add_filter('user_id', '=', user_info['user_id'])
    result = list(query.fetch())
    return result


@app.route('/', methods=["GET", "POST"])
def root():
    id_token = request.cookies.get("token")
    error_message = None
    claims = None
    user_info = None
    gallery_info = None
    success=None
    duplicate_images_urls = []
    if id_token:
        try:
            claims = google.oauth2.id_token.verify_firebase_token(id_token, firebase_request_adapter)
            user_info = retrieveUserInfo(claims)
            if user_info is not None:
                gallery_info = retrieveGalleries(user_info)
                allImagesOfUser = getTotalImagesOfUser(user_info)
                duplicate_images_urls = duplicate_images(allImagesOfUser)
            if user_info == None:
                createUserInfo(claims)
                user_info = retrieveUserInfo(claims)
        except ValueError as exc:
            error_message = str(exc)
    return render_template('index.html', user_data=claims, error_message=error_message, userData=user_info,galleries=gallery_info, success = success,duplicate_images_urls=duplicate_images_urls)

@app.route('/addgallery',methods=["GET", "POST"])
def addpost():
    id_token = request.cookies.get("token")
    error_message = None
    claims = None
    user_info = None
    success=None
    if id_token:
        try:
            claims = google.oauth2.id_token.verify_firebase_token(id_token, firebase_request_adapter)
            user_info = retrieveUserInfo(claims)
            if request.method == 'POST':
                    gallery_id = str(uuid.uuid4())
                    gallery_name = request.form.get('galleryName')
                    gallery_duplicate = getGalleryNameExistsOrNot(name=gallery_name, user_id=user_info['user_id'])
                    if gallery_duplicate:
                        error_message = "Gallery name already exists!"
                    else:
                        entity = datastore.Entity(key=datastore_client.key('gallery_data',gallery_id))
                        entity.update({
                            'gallery_id': gallery_id,
                            'gallery_name': gallery_name,
                            'user_id': user_info['user_id'],
                        })
                        datastore_client.put(entity)
                        success = True
        except ValueError as exc:
            error_message = str(exc)
        return render_template('creategallery.html',  error_message=error_message, userData=user_info, success = success)
    else:
        return redirect('/')

@app.route('/deletegallery', methods=["GET", "POST"])
def deletegallery():
    id_token = request.cookies.get("token")
    error_message = None
    claims = None
    user_info = None
    success = None
    if id_token:
        try:
            claims = google.oauth2.id_token.verify_firebase_token(id_token, firebase_request_adapter)
            user_info = retrieveUserInfo(claims)
            if request.method == 'POST':
                datastore_client.delete(datastore_client.key('gallery_data', request.form.get('gallery_id')))
                return redirect('/')
        except ValueError as exc:
            error_message = str(exc)
        return render_template('deletegallery.html', error_message=error_message, userData=user_info, success=success)
    else:
        return redirect('/')

@app.route('/editgallery',methods=["GET", "POST"])
def editgalleryname():
    id_token = request.cookies.get("token")
    error_message = None
    claims = None
    user_info = None
    success=None
    singlegalleryinfo = None
    gallery_id = None
    if id_token:
        try:
            claims = google.oauth2.id_token.verify_firebase_token(id_token, firebase_request_adapter)
            user_info = retrieveUserInfo(claims)
            gallery_id = request.args.get('id')
            singlegalleryinfo = getSingleGalleryInfo(request.args.get('id'))     
            # if user_info:
            #     gallery_id = request.args.get('id') 
            #     singlegalleryinfo = getSingleGalleryInfo(request.args.get('id'))     
            if request.method == 'POST':
                    new_gallery_name = request.form.get('new_gallery_name')
                    singlegalleryinfo['gallery_name'] = new_gallery_name
                    datastore_client.put(singlegalleryinfo)
                    success = True
        except ValueError as exc:
            error_message = str(exc)
        return render_template('editgallery.html',  error_message=error_message, userData=user_info,gallery_data = singlegalleryinfo, success = success,gallery_id=gallery_id)
    else:
        return redirect('/')

@app.route('/preview',methods=["GET", "POST"])
def gallerypreview():
    id_token = request.cookies.get("token")
    error_message = None
    claims = None
    user_info = None
    success=None
    obj =None
    duplicate_images_urls = []
    if id_token:
        try:
            claims = google.oauth2.id_token.verify_firebase_token(id_token, firebase_request_adapter)
            user_info = retrieveUserInfo(claims)
            GalleryImages = getGalleryImages(user_info,request.args.get('id'))
            entity_key = datastore_client.key('gallery_data', "gallery test one")
            obj = datastore_client.get(entity_key)
            if request.method == 'POST':
                if 'image' in request.files:
                    image_file = request.files.get('image')
                    if image_file and allowed_file(image_file.filename):
                        image_id = str(uuid.uuid4())
                        image_blob = bucket.blob(image_id)
                        image_blob.upload_from_file(image_file)
                        image_blob.make_public()
                        image_url = image_blob.public_url
                        entity = datastore.Entity(key=datastore_client.key('images_data',image_id))
                        entity.update({
                            'image_id': image_id,
                            'gallery_id': request.args.get('id'),
                            'user_id': user_info['user_id'],
                            'image_url':image_url,
                            'createdtime':datetime.now(),
                        })
                        datastore_client.put(entity)
                        success = True
                    else:
                        error_message = 'Invalid file type. Only JPE,JPEG and PNG files are allowed.'
                elif 'image_id_to_delete' in request.form:
                    datastore_client.delete(datastore_client.key('images_data', request.form.get('image_id_to_delete')))
                GalleryImages = getGalleryImages(user_info,request.args.get('id'))
            duplicate_images_urls = duplicate_images(GalleryImages)
        except ValueError as exc:
            error_message = str(exc)
        return render_template('gallerypreview.html',  error_message=error_message, userData=user_info, success = success,GalleryImages=GalleryImages,singlegalleryinfo=obj,duplicate_images_urls=duplicate_images_urls)
    else:
        return redirect('/')



if __name__ == '__main__':
 app.run(host='127.0.0.1', port=8081, debug=True)