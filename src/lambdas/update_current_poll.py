import boto3
import hashlib
import time
from botocore.exceptions import ClientError
        
dynamodb = boto3.resource('dynamodb')

def hash_password(password, salt):
    """Using the sha256 crypto algorithm hash the combination of password and salt in 10 iterations.
    
    Parameters:
        password: Password.
        salt: Salt.
    
    Returns:
        Hashed password.
    """

    hashed_password = password

    for i in range(10):
        salted_password = (salt + hashed_password).encode('utf-8')
        hashed_password = hashlib.sha256(salted_password).hexdigest()

    return hashed_password

def get_current_poll_id(second_attempt = False):
    """Tries 2 times to access the config table and take the current poll id.

    Parameters:
        second_attempt: Flag for the second attempt.

    Returns:
        Current poll id.
    """

    config_table = dynamodb.Table('fp.config')

    try:
        response = config_table.get_item(
            Key={
                'id': 'CurrentPoll'
            }
        )
    except Exception:
        if second_attempt:
            raise Exception('Database error!')

        # tries again if the first attempt failed
        time.sleep(1)
        return get_current_poll_id(True)
        
    return int(response['Item']['value'])

def update_current_poll(event, context):
    """Updates the current poll, admin credentials are mandatory

    Returns:
        Status of updating.
    """

    # check admin credentials
    if ('admin_name' not in event) or ('admin_password' not in event):
        return {
            'statusCode': 403,
            'errorMessage': 'Access denied, missing admin_name and/or admin_password!'
        }
    
    admin_name = event['admin_name']
    admin_password = event['admin_password']
    
    admins_table = dynamodb.Table('fp.admins')

    try:
        admin = admins_table.get_item(
            Key={
                'name': admin_name
            }
        )
    except Exception:
        return {
            'statusCode': 500,
            'errorMessage': 'Database error!'
        }

    if 'Item' not in admin:
        return {
            'statusCode': 403,
            'errorMessage': 'Access denied, wrong credentials!'
        }
    
    db_hashed_password = admin['Item']['password']
    db_salt = admin['Item']['salt']

    hashed_password = hash_password(admin_password, db_salt)

    if db_hashed_password != hashed_password:
        return {
            'statusCode': 403,
            'errorMessage': 'Access denied, wrong credentials!'
        }

    # check properties for updating
    properties = ['title', 'note', 'locUrl', 'locDesc', 'max', 'need', 'end', 'dt']
    update_properties = {}
    found = False

    for prop in properties:
        update_properties[prop] = None

        if prop in event:
            update_properties[prop] = event[prop]
            found = True

    if not found:
        return {
            'statusCode': 400,
            'errorMessage': 'Nothing to update!'
        }

    # check string lengths
    if (update_properties['title'] != None) and (len(update_properties['title']) > 50):
        return { 
            'statusCode': 400,
            'errorMessage': 'Too long title!'
        }

    if (update_properties['note'] != None) and (len(update_properties['note']) > 100):
        return { 
            'statusCode': 400,
            'errorMessage': 'Too long note!'
        }
    
    if (update_properties['locUrl'] != None) and (len(update_properties['locUrl']) > 100):
        return { 
            'statusCode': 400,
            'errorMessage': 'Too long locUrl!'
        }
    
    if (update_properties['locDesc'] != None) and (len(update_properties['locDesc']) > 50):
        return { 
            'statusCode': 400,
            'errorMessage': 'Too long locDesc!'
        }
    
    for prop in ['max', 'need', 'end', 'dt']:
        if prop in event:
            try:
                update_properties[prop] = int(update_properties[prop])
            except:
                return {
                    'statusCode': 400,
                    'errorMessage': prop + ' value is not an integer number!'
                }

    # check int values
    if (update_properties['dt'] != None) and (update_properties['dt'] < 0):
        return { 
            'statusCode': 400,
            'errorMessage': 'dt value shouldn\'t be negative!'
        }

    if (update_properties['end'] != None) and (update_properties['end'] < 0):
        return { 
            'statusCode': 400,
            'errorMessage': 'end value shouldn\'t be negative!'
        }

    if (update_properties['need'] != None) and (update_properties['need'] < 1):
        return { 
            'statusCode': 400,
            'errorMessage': 'need value should be bigger than 1!'
        }

    if (update_properties['max'] != None) and (update_properties['max'] < 1):
        return { 
            'statusCode': 400,
            'errorMessage': 'max value should be bigger than 1!'
        }

    # check if dt is smaller than end
    if (update_properties['end'] != None) and (update_properties['dt'] != None) and (update_properties['dt'] > update_properties['end']):
        return { 
            'statusCode': 400,
            'errorMessage': 'dt value must be smaller or equal than end value!'
        }

    # check if max is smaller than need
    if (update_properties['max'] != None) and (update_properties['need'] != None) and (update_properties['max'] > update_properties['need']):
        return { 
            'statusCode': 400,
            'errorMessage': 'need value must be smaller or equal than max value!'
        }

    # prepare the expressions for the update query
    update_expression = "SET "
    expression_attributes = {}
    expression_names = {}

    for prop in properties:
        if update_properties[prop] == None:
            del update_properties[prop]
        else:
            prop_name = '#' + prop
            prop_value = ':' + prop
            update_expression += prop_name + '= ' + prop_value + ', '
            expression_names[prop_name] = prop # avoid reserved words
            expression_attributes[prop_value] = update_properties[prop]

    expression_names['#end'] = 'end'
    expression_names['#start'] = 'start'
    expression_names['#need'] = 'need'
    expression_names['#max'] = 'max'

    update_expression = update_expression[:-2]

    expression_attributes[':none'] = 'None'
    expression_attributes[':end'] = 'None' if ('end' not in update_properties) else update_properties['end']
    expression_attributes[':dt'] = 'None' if ('dt' not in update_properties) else update_properties['dt']
    expression_attributes[':need'] = 'None' if ('need' not in update_properties) else update_properties['need']
    expression_attributes[':max'] = 'None' if ('max' not in update_properties) else update_properties['max']

    # get current poll id
    try:
        current_poll_id = get_current_poll_id()
    except Exception:
        return {
            'statusCode': 500,
            'errorMessage': 'Database error!'
        }

    # update the current poll
    polls_table = dynamodb.Table('fp.polls')

    try:
        polls_table.update_item(
            Key={
                'id': current_poll_id
            },
            UpdateExpression=update_expression,
            # check if new end new and dt are bigger than start, and if there is no new end check if the new dt is smaller than the old end
            # check if need is smaller or equal to max
            ConditionExpression='(:end = :none OR :end > #start) AND (:dt = :none OR (:dt > #start AND (:end <> :none OR :dt <= #end))) AND (:need = :none OR :need <= #max) AND (:max = :none OR :max >= #need)',
            ExpressionAttributeValues=expression_attributes,
            ExpressionAttributeNames=expression_names
        )
    except ClientError as e:
        if e.response['Error']['Code'] == "ConditionalCheckFailedException":
            return { 
                'statusCode': 400,
                'errorMessage': e.response['Error']['Message'] + '!'
            }
        
        return {
            'statusCode': 500,
            'errorMessage': 'Database error!'
        }

    return {
        'statusCode': 200,
        'statusMessage': 'The current poll is successfully updated!'
    }