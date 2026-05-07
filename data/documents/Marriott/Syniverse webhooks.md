
{    
  "topic":"SCG-Message",  
  "attempt":1,  
  "event":{    
      "fld-val-list":{    
        "sender_id_alias":"xxxxxxxxxxxxxxxxxxxxxxx",  
        "mo_price":0.005,  
        "company-id":xxx,  
        "sender_id_id":"xxxxxxxxxxxxxxxxxxxxxxxxxx",  
        "message_body":"Test MO message",  
        "message_id":"6QX2csWrr064RzxhwHo0m7",  
        "to_address":"66000",  
        "has_attachment":false,  
        "fragments_count":1,  
        "from_address":"+14085551212",  
        "application_id":304  
      },  
      "evt-tp":"mo_message_received",  
      "timestamp":"2017-11-30T17:17:46.615Z"  
  },  
  "event-id":"jX5nAV9USriK2LkS6e0D0g"  
}  
  
  
In Reality, It is posting like below:  
**(MO) Mobile Origination event:**  
{  
"country": "USA",  
"mo_price": 0,  
"message_id": "e6Ogb0EUXYp2V2b50m8F27WK43",  
"to_address": "18338580861",  
"has_attachment": false,  
"application_id": 6976,  
"carrier_id": "2473",  
"sender_id_alias": "nxbX4PzLqFq0fVv9WqEW23",  
"company-id": 109938,  
"sender_id_id": "nxbX4PzLqFq0fVv9WqEW23", --> Yes  
"message_body": "Ty for your msg from Marriott property2",  
"fragments_count": 1,  
"from_address": "+17409170707",  
"carrier_name": "Google Voice",  
"anti_virus_scan_status": "NONE"  
}