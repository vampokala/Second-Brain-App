curl --location 'https://api.syniverse.com/engage/sdc-account -

creation/v1/companies/sub_companies'

--header 'Authorization: Bearer Token’

--header 'Content-Type: application/json' \

--data-raw '{

"company_nm": "ECMP-NON-PROD",

"username": " vpoka217",

"user_email": " vamshi.pokala@marriott.com",

"first_name": " Vamshi",

"last_name": " Pokala",

"country": " USA",

"state": " MA",

"account_id": 26584 , 

"sub_account_name": " ECMP_QA",

"sub_application_name": " ECMP QA",

"api_token_expire_time_in_sec": -1

}'