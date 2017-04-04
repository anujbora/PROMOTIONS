# Copyright 2016, 2017 John J. Rofrano. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import logging
from threading import Lock
from flask import Flask, Response, jsonify, request, make_response, json, url_for, render_template
from flask_api import status    # HTTP Status Codes
from redis import Redis
from redis.exceptions import ConnectionError
from promotion import Promotion

# Create Flask application
app = Flask(__name__)
app.config['LOGGING_LEVEL'] = logging.INFO

# Status Codes
HTTP_200_OK = 200
HTTP_201_CREATED = 201
HTTP_204_NO_CONTENT = 204
HTTP_400_BAD_REQUEST = 400
HTTP_404_NOT_FOUND = 404
HTTP_409_CONFLICT = 409

######################################################################
# GET INDEX
######################################################################
@app.route('/')
def index():
    return render_template('index.html')
    #promotion_url = request.base_url + "promotions"
    #return make_response(jsonify(name='Promotion REST API Service',version='1.0',url=promotion_url), HTTP_200_OK)

######################################################################
# LIST ALL PROMOTIONS
######################################################################
@app.route('/promotions', methods=['GET'])
def list_promotions():
    results = []
    
    kind = request.args.get('kind')
    id = request.args.get('id')
    if kind:
        result = Promotion.find_by_kind(redis, kind)
    else:
        result = Promotion.all(redis)
    if len(result) > 0:
       results = [Promotion.serialize(promotion) for promotion in result]
       return make_response(jsonify(results), HTTP_200_OK)
    else:
       results = { 'error' : 'No promotions found'  }
       rc = HTTP_404_NOT_FOUND
       return make_response(jsonify(results), rc)

######################################################################
# LIST ALL ACTIVE PROMOTIONS
######################################################################
@app.route('/promotions/status/active', methods=['GET'])
def list_all_active_promotions():
    results = Promotion.find_by_status(redis, 'ACTIVE')
    if len(results) > 0:
        result = [Promotion.serialize(promotion) for promotion in results]
        rc = HTTP_200_OK
    else:
        result = { 'error' : 'No active promotions found'  }
        rc = HTTP_404_NOT_FOUND

    return make_response(jsonify(result), rc)

######################################################################
# RETRIEVE A PROMOTION
######################################################################
@app.route('/promotions/<int:id>', methods=['GET'])
def get_promotions(id):
    promotion = Promotion.find(redis, id)
    if promotion:
        message = promotion.serialize()
        rc = HTTP_200_OK
    else:
        message = { 'error' : 'Promotion with id: %s was not found' % str(id) }
        rc = HTTP_404_NOT_FOUND

    return make_response(jsonify(message), rc)

######################################################################
# RETRIEVE ALL PROMOTIONS BASED ON KIND
######################################################################
@app.route('/promotions/kind/<kind>', methods=['GET'])
def get_promotions_kind(kind):
    results = Promotion.find_by_kind(redis, kind.upper())
    if len(results) > 0:
        result = [Promotion.serialize(promotion) for promotion in results]
        rc = HTTP_200_OK
    else:
        result = { 'error' : 'Promotion with kind: %s was not found' % str(kind)  }
        rc = HTTP_404_NOT_FOUND

    return make_response(jsonify(result), rc)

######################################################################
# ACTION TO CANCEL THE PROMOTION
######################################################################
@app.route('/promotions/<int:id>/cancel', methods=['PUT'])
def cancel_promotions(id):
    promotion = Promotion.find(redis, id)
    if promotion:
        promotion = Promotion.cancel_by_id(redis,id)
        promotion.save(redis)
        message = {'Success' : 'Cancelled the Promotion with id ' + str(id)}
        rc = HTTP_200_OK
    else:
        message = { 'error' : 'Promotion %s was not found' % id }
        rc = HTTP_404_NOT_FOUND

    return make_response(jsonify(message), rc)

######################################################################
# ADD A NEW PROMOTION
######################################################################
@app.route('/promotions', methods=['POST'])
def create_promotions():
    id = 0
    payload = request.get_json()
    print payload
    if Promotion.validate(payload):
        promotion = Promotion(id, payload['name'], payload['description'], payload['kind'], 'Active')
        promotion.save(redis)
        id = promotion.id
        message = promotion.serialize()
        rc = HTTP_201_CREATED
    else:
        message = { 'error' : 'Data is not valid' }
        rc = HTTP_400_BAD_REQUEST

    response = make_response(jsonify(message), rc)
    if rc == HTTP_201_CREATED:
        response.headers['Location'] = url_for('get_promotions', id=id)
    return response

######################################################################
# UPDATE AN EXISTING PROMOTION
######################################################################
@app.route('/promotions/<int:id>', methods=['PUT'])
def update_promotions(id):
    promotion = Promotion.find(redis, id)
    if promotion:
        payload = request.get_json()
        payload['id']=id
        print 'payload is',payload
        if Promotion.validate(payload):
            promotion = Promotion.from_dict(payload)
            promotion.save(redis)
            message = promotion.serialize()
            rc = HTTP_200_OK
        else:
            message = { 'error' : 'Promotion data was not valid' }
            rc = HTTP_400_BAD_REQUEST
    else:
        message = { 'error' : 'Promotion %s was not found' % id }
        rc = HTTP_404_NOT_FOUND
    return make_response(jsonify(message), rc)

######################################################################
# LIST ALL INACTIVE PROMOTIONS
######################################################################
@app.route('/promotions/status/inactive', methods=['GET'])
def list_all_inactive_promotions():
    results = Promotion.find_by_status(redis, 'INACTIVE')
    if len(results) > 0:
        result = [Promotion.serialize(promotion) for promotion in results]
        rc = HTTP_200_OK
    else:
        result = { 'error' : 'No active promotions found'  }
        rc = HTTP_404_NOT_FOUND
    return make_response(jsonify(result), rc)

######################################################################
# DELETE A PROMOTION
######################################################################
@app.route('/promotions/<int:id>', methods=['DELETE'])
def delete_promotions(id):
    promotion = Promotion.find(redis, id)
    if promotion:
       promotion.delete(redis)
    return make_response('', HTTP_204_NO_CONTENT)

######################################################################
#  U T I L I T Y   F U N C T I O N S
######################################################################
def data_load(payload):
    promotion = Promotion(0, payload['name'], payload['description'], payload['kind'],payload['status'])
    promotion.save(redis)

def data_reset():
    redis.flushall()

@app.before_first_request
def setup_logging():
    if not app.debug:
        # In production mode, add log handler to sys.stderr.
        handler = logging.StreamHandler()
        handler.setLevel(app.config['LOGGING_LEVEL'])
        # formatter = logging.Formatter(app.config['LOGGING_FORMAT'])
        #'%Y-%m-%d %H:%M:%S'
        formatter = logging.Formatter('[%(asctime)s] - %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]')
        handler.setFormatter(formatter)
        app.logger.addHandler(handler)

######################################################################
# Connect to Redis and catch connection exceptions
######################################################################
def connect_to_redis(hostname, port, password):
    redis = Redis(host=hostname, port=port, password=password)
    try:
        redis.ping()
    except ConnectionError:
        redis = None
    return redis


######################################################################
# INITIALIZE Redis
# This method will work in the following conditions:
#   1) In Bluemix with Redis bound through VCAP_SERVICES
#   2) With Redis running on the local server as with Travis CI
#   3) With Redis --link ed in a Docker container called 'redis'
######################################################################
def inititalize_redis():
    global redis
    redis = None
    # Get the crdentials from the Bluemix environment
    if 'VCAP_SERVICES' in os.environ:
        app.logger.info("Using VCAP_SERVICES...")
        VCAP_SERVICES = os.environ['VCAP_SERVICES']
        services = json.loads(VCAP_SERVICES)
        creds = services['rediscloud'][0]['credentials']
        app.logger.info("Conecting to Redis on host %s port %s" % (creds['hostname'], creds['port']))
        redis = connect_to_redis(creds['hostname'], creds['port'], creds['password'])
    else:
        app.logger.info("VCAP_SERVICES not found, checking localhost for Redis")
        redis = connect_to_redis('127.0.0.1', 6379, None)
        if not redis:
            app.logger.info("No Redis on localhost, using: redis")
            redis = connect_to_redis('redis', 6379, None)
    if not redis:
        # if you end up here, redis instance is down.
        app.logger.error('*** FATAL ERROR: Could not connect to the Redis Service')
        exit(1) 

######################################################################
#   M A I N
######################################################################
if __name__ == "__main__":
    # Pull options from environment
    debug = (os.getenv('DEBUG', 'False') == 'True')
    inititalize_redis()
    port = os.getenv('PORT', '5000')
    app.run(host='0.0.0.0', port=int(port), debug=debug)
