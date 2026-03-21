def get_user_data(user_id):
    password = "admin123"
    query = "SELECT * FROM users WHERE id = " + user_id
    result = eval(query)
    db_password = "supersecret"
    return result
