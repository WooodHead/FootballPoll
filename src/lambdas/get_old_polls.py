import boto3
import time
        
dynamodb = boto3.resource('dynamodb')

def batch_get_items(keys, second_attempt = False):
    """Performs batch get items on polls table, uf the first attempt has unprocessed keys tries again.

    Parameters:
        keys: List with keys of polls.
        second_attempt: Flag for the second attempt.

    Returns:
        List of max 5 polls.
    """

    result = []

    if len(keys) != 0:
        try:
            response = dynamodb.batch_get_item(
                RequestItems={
                    'fp.polls': {
                        'Keys': keys
                    }
                }   
            )
        except Exception:
            raise Exception('Database error!')
        else:
            if ('Responses' not in response) or ('fp.polls' not in response['Responses']):
                raise Exception('Database error!')
            
            result = response['Responses']['fp.polls']

            if second_attempt:
                return result
            
            if ('UnprocessedKeys' in response) and ('fp.polls' in response['UnprocessedKeys']) and ('Keys' in response['UnprocessedKeys']['fp.polls']):
                try:
                    time.sleep(1)
                    second_response = batch_get_items(response['UnprocessedKeys']['fp.polls']['Keys'], True)
                except Exception:
                    pass
                else:
                    if ('Responses' in second_response) and ('fp.polls' in second_response['Responses']):
                        result.append(second_response)
        
    return result

def get_old_polls(event, context):
    """Returns at most 5 polls older than the last_poll.

    Returns:
        List of max 5 polls.
    """

    if 'last_poll' not in event:
        return {
            'statusCode': 400,
            'errorMessage': 'last_poll parameter doesn\'t exist in the API call!'
        }

    try:
        last_poll = int(event['last_poll'])
    except:
        return {
            'statusCode': 400,
            'errorMessage': 'last_poll value is not an integer number!'
        }
    
    polls = []
    first_poll = max(last_poll - 5, 0)
    keys = [{'id': id} for id in range(first_poll, last_poll)]

    try:
        response = batch_get_items(keys)
    except Exception:
        return {
            'statusCode': 500,
            'errorMessage': 'Database error!'
        }
    else:
        polls = response

    return {
        'statusCode': 200,
        'body': polls
    }