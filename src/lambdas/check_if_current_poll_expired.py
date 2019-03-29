import boto3
import time
from boto3.dynamodb.conditions import Key

dynamodb = boto3.resource('dynamodb')

def get_current_poll_id():
    """Tries to access the config table and take the current poll id, tries until the query succeeded.

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
        # tries again
        time.sleep(1)
        return get_current_poll_id()
        
    return int(response['Item']['value'])

def get_item_polls(poll_id):
    """Tries to access the polls table and take the current poll, tries until the query succeeded.

    Returns:
        Current poll item.
    """

    polls_table = dynamodb.Table('fp.polls')

    try:
        response = polls_table.get_item(
            Key={
                'id': poll_id
            }
        )
    except Exception:
        # tries again
        time.sleep(1)
        return get_item_polls(poll_id)
        
    return response['Item']

def query_participants(poll_id, last_evaluated_key = None):
    """Query the participants table and returns all results for given poll, tries until the query succeeded.

    Parameters:
        last_evaluated_key: Last evaluated key, if some data is not read.

    Returns:
        List with participants.
    """
    
    result = []

    participants_table = dynamodb.Table('fp.participants')

    try:
        if last_evaluated_key:
            response = participants_table.query(
                KeyConditionExpression=Key('poll').eq(poll_id),
                ExclusiveStartKey=last_evaluated_key
            )
        else:
            response = participants_table.query(
                KeyConditionExpression=Key('poll').eq(poll_id)
            )
    except Exception:
        # tries again
        time.sleep(1)
        return query_participants(poll_id, last_evaluated_key)
       
    if 'Items' in response:
        result = response['Items']

    if 'LastEvaluatedKey' in response:
        # tries again if there are unprocessed keys
        try:
            time.sleep(1)
            second_result = query_participants(poll_id, response['LastEvaluatedKey'])
        except Exception:
            # the first response is successful, returns only the results from the first response
            pass
        else:
            result.append(second_result)
    
    return result

def scan_persons(last_evaluated_key = None):
    """Scans the persons table and returns all results, tries until the query succeeded.

    Parameters:
        last_evaluated_key: Last evaluated key, if some data is not read.

    Returns:
        List with persons.
    """

    result = []

    persons_table = dynamodb.Table('fp.persons')

    try:
        response = persons_table.scan(ExclusiveStartKey=last_evaluated_key) if last_evaluated_key else persons_table.scan()
    except Exception:
        # tries again
        time.sleep(1)
        return scan_persons(last_evaluated_key)

    if 'Items' in response:
        result = response['Items']

    if 'LastEvaluatedKey' in response:
        # tries again if there are unprocessed keys
        try:
            time.sleep(1)
            second_result = scan_persons(response['LastEvaluatedKey'])
        except Exception:
            # the first response is successful, returns only the results from the first response
            pass
        else:
            result.append(second_result)
    
    return result

def put_item_polls(item):
    """Tries to add the new poll until the query succeeded.

    Parameters:
        item: New polls item.
    """

    polls_table = dynamodb.Table('fp.polls')

    try:
        polls_table.put_item(
            Item=item
        )
    except Exception:
        # tries again
        time.sleep(1)
        put_item_polls(item)

def update_item_config(new_poll_id):
    """Tries to update the config (new current poll id) until the query succeeded.

    Parameters:
        new_poll_id: New poll id.
    """

    config_table = dynamodb.Table('fp.config')

    try:
        config_table.update_item(
            Key={
                'id': 'CurrentPoll'
            },
            UpdateExpression="set #value = :value",
            ExpressionAttributeNames={
                '#value': 'value'
            },
            ExpressionAttributeValues={
                ':value': new_poll_id
            }
        )
    except Exception:
        # tries again
        time.sleep(1)
        update_item_config(new_poll_id)

def check_if_current_poll_expired(event, context):
    """.

    Returns:
        Status of the function.
    """

    # get current id
    current_poll_id = get_current_poll_id()

    # get current poll
    current_poll = get_item_polls(current_poll_id)

    ###
    """ TODO: check if expired """
    ###

    # get current participants
    participants = query_participants(current_poll_id)

    # get persons
    persons = scan_persons()

    ###
    """ TODO: find new unique persons """
    ###

    # batch write - add new persons (if there is new person/s)

    ###
    """ TODO: find persons that need to be updated """
    ###

    # update persons

    # add new poll
    new_poll_id = current_poll_id + 1
    week_milliseconds = 1000 * 60 * 60 * 24 * 7

    put_item_polls({
        'id': new_poll_id,
        'start': current_poll['start'] + week_milliseconds,
        'end': current_poll['end'] + week_milliseconds,
        'dt': current_poll['dt'] + week_milliseconds,
        'title': current_poll['title'],
        'note': current_poll['note'],
        'locDesc': current_poll['locDesc'],
        'locUrl': current_poll['locUrl'],
        'need': current_poll['need'],
        'max': current_poll['max']
    })
    
    # update current id
    update_item_config(new_poll_id)

    return {
        'statusCode': 200,
        'statusMessage': 'New poll is started successfully!'
    }