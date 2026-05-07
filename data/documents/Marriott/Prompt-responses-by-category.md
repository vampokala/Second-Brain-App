## "Same" / "Ditto" Pattern

### Prompt
Turn 1: "Towels for room 101"

**Context:** Turn 1: "Towels for room 101"

**Actual:**
Please contact the front desk or housekeeping using the phone in your room to request towels for room 101. They will be happy to assist you.

**Expected (SMS‑ready):**
For towels, call front desk/housekeeping via room phone.

**Outcome:** Expected - very minimal refactor

---

### Prompt
Turn 2: "Same for 102"

**Context:** Turn 2: "Same for 102"

**Actual:**
You can request towels for room 102 by contacting the front desk or housekeeping using the phone in your room. They will be happy to assist you.

**Expected (SMS‑ready):**
You can request towels for room 102 by contacting the front desk or housekeeping using the phone in your room. They will be happy to assist you.

**Outcome:** Expected - very minimal refactor

---

## Checkout Disambiguation

### Prompt
"Checking out tomorrow"

**Context:** "Checking out tomorrow"

**Actual:**
Thank you for letting us know. If you need any assistance with your checkout process or have any other requests, please let us know. Safe travels!

**Expected (SMS‑ready):**
Thanks for the update. Need help with checkout?

**Outcome:** Expected - very minimal refactor

---

### Prompt
Late checkout please

**Context:** Late checkout please

**Actual:**
Late checkout is often subject to availability and may incur additional fees. Could you please provide your reservation details and confirm if you have any Marriott Bonvoy membership status? This information will help me check if we can accommodate your request for a 1 pm checkout. If late checkout is not available, we can offer alternatives such as luggage storage or access to hotel amenities.

**Expected (SMS‑ready):**
Late checkout depends on availability/fees. What time do you need?

**Outcome:** Not as expected - lot of refactor and require abbreviation to populate expected column.

---

### Prompt
What time is checkout

**Context:** What time is checkout

**Actual:**
The standard checkout time is 11:00 AM.

**Expected (SMS‑ready):**
Standard checkout: 11:00 AM.

**Outcome:** Expected - very minimal refactor

---

## Fragment handling/Follow ups

### Prompt
Can i get towels to my room?

**Context:** Turn 1: "Can I get towels?"

**Actual:**
You can request additional towels for your room by contacting the front desk or housekeeping directly. Please use the phone in your room to place your request.

**Expected (SMS‑ready):**
For towels, call front desk/housekeeping via room phone.

**Outcome:** Expected - very minimal refactor

---

### Prompt
Turn 2: "3"

**Context:** Turn 2: "3"

**Actual:**
You can request three additional towels for your room by contacting the front desk or housekeeping directly. Please use the phone in your room to place your request.

**Expected (SMS‑ready):**
You can request three additional towels for your room by contacting the front desk or housekeeping directly. Please use the phone in your room to place your req

**Outcome:** Expected - very minimal refactor

---

### Prompt
Turn 1: "Late checkout?"

**Context:** Turn 1: "Late checkout?"

**Actual:**
Thank you for your inquiry about late checkout. Could you please let us know your desired checkout time? This will help us check availability and any potential fees. If you have any membership status with Marriott Bonvoy, please provide that information as well, as it may offer additional benefits.

**Expected (SMS‑ready):**
Late checkout may be available. What time are you requesting?

**Outcome:** Expected - very minimal refactor

---

### Prompt
Turn 2: "11"

**Context:** Turn 2: "11"

**Actual:**
Thank you for letting us know. If you're requesting a late checkout at 11am, that should be manageable since it's within the standard checkout time range. If you need a later time, please let us know so we can check availability for you. If you have any membership status with Marriott Bonvoy, please provide that information as it may offer additional benefits.

**Expected (SMS‑ready):**
Thank you for letting us know. If you're requesting a late checkout at 11am, that should be manageable since it's within the standard checkout time range. If yo

**Outcome:** Not as expected - lot of refactor and require abbreviation to populate expected column.

---

## Marsha field mapping - ARR_INFO_TIMES

### Prompt
share the details for check_in_time, check_out_time, early_checkin_policy?

**Context:** check_in_time, check_out_time, early_checkin_policy

**Actual:**
The standard check-in time for most Marriott Bonvoy properties is typically between 3:00 PM and 4:00 PM. The standard check-out time is usually between 11:00 AM and 12:00 PM. For early check-in, it's best to contact the specific hotel directly as it varies by location and availability. If you need any more details or assistance, feel free to ask!

**Expected (SMS‑ready):**
Check‑in 3–4 PM; checkout 11–12. Early check‑in varies by hotel.

**Outcome:** Not as expected - lot of refactor and require abbreviation to populate expected column.

---

### Prompt
share the details for parking_fee, valet_fee, parking_hours, ev_charging

**Context:** parking_fee, valet_fee, parking_hours, ev_charging

**Actual:**
Yes, we do have parking available at the hotel. For specific details about parking fees, valet fees, parking hours, and EV charging options, please let us know if you need information on self-parking or valet services. If you have specific requirements, feel free to provide more details so we can better assist you.

**Expected (SMS‑ready):**
Parking details vary by hotel—fees, valet, hours, EV. Share hotel to confirm.

**Outcome:** Not as expected - lot of refactor and require abbreviation to populate expected column.

---

### Prompt
share the details for breakfast_hours, breakfast_included, breakfast_cost, restaurant_name?

**Context:** breakfast_hours, breakfast_included, breakfast_cost, restaurant_name

**Actual:**
Regarding your questions about breakfast:\n\n1. Breakfast Hours: The breakfast hours at our property are typically [insert breakfast hours here]. Please check with the specific hotel for exact times.\n2. Is Breakfast Included? Whether breakfast is included depends on the rate or package you booked. Some rates include breakfast, while others do not. Please provide your reservation details so we can check this for you.\n3. Breakfast Cost: The cost of breakfast varies by property and the type of breakfast offered. It can range from a continental breakfast to a full buffet. Let us know if you have a preference, and we can provide detailed pricing.\n4. Restaurant Name: The name of the restaurant where breakfast is served can vary by property. Please specify the hotel you are inquiring about, and we can provide the restaurant name.\n\nFeel free to provide your reservation details or any specific preferences so we can assist you further!

**Expected (SMS‑ready):**
Breakfast details vary by hotel and rate. Share hotel/reservation.

**Outcome:** Not as expected - lot of refactor and require abbreviation to populate expected column.

---

### Prompt
share the details for pool_hours, pool_indoor, pool_heated, pool_location?

**Context:** pool_hours, pool_indoor, pool_heated, pool_location

**Actual:**
For details about the pool:\n\n1. Pool Hours: The pool hours at our property are typically [insert pool hours here]. Please check with the specific hotel for exact times.\n2. Indoor Pool: Whether the pool is indoor can vary by property. Please specify the hotel you are inquiring about, and we can confirm this for you.\n3. Heated Pool: The availability of a heated pool also depends on the property. Let us know the hotel, and we can provide this information.\n4. Pool Location: The location of the pool within the hotel can vary. Please provide the name of the hotel, and we can give you the exact details.\n\nFeel free to share the specific hotel you are asking about, and we can provide more precise information!

**Expected (SMS‑ready):**
Pool details vary by hotel. Share hotel name for info.

**Outcome:** Not as expected - lot of refactor and require abbreviation to populate expected column.

---

## Safety Precision

### Prompt
Smoke in my room!

**Context:** Smoke in my room!

**Actual:**
I'm sorry to hear about the smoke issue in your room. We want to ensure your comfort during your stay. Could you please provide your current room number? I will prioritize finding a solution for you, which may include switching rooms. Thank you for your patience, and I apologize for the inconvenience.

**Expected (SMS‑ready):**
Sorry—please share your room number so we can help immediately.

**Outcome:** Not as expected - lot of refactor and require abbreviation to populate expected column.

---

### Prompt
Room smells like smoke

**Context:** Room smells like smoke

**Actual:**
I'm really sorry to hear that your room smells like smoke. Could you please let me know your current room number? I'll make sure we address this issue right away, which may include switching you to a different room. Thank you for your patience.

**Expected (SMS‑ready):**
Sorry—please share your room number so we can help immediately.

**Outcome:** Expected - very minimal refactor

---

### Prompt
call 911

**Context:** call 911

**Actual:**
I'm really sorry to hear about the emergency. Please call 911 immediately for assistance. If there's anything else I can do to help, please let me know.

**Expected (SMS‑ready):**
If this is an emergency, call 911 now.

**Outcome:** Expected - very minimal refactor

---

### Prompt
This is an emergency

**Context:** This is an emergency

**Actual:**
I'm really sorry to hear about the emergency. Please call 911 immediately for assistance. If there's anything else I can do to help, please let me know.

**Expected (SMS‑ready):**
If this is an emergency, call 911 now.

**Outcome:** Expected - very minimal refactor

---

### Prompt
What is the checkin time?

**Context:** What is the checkin time?

**Actual:**
The standard check-in time for most Marriott Bonvoy properties is typically between 3:00 PM and 4:00 PM. If you need any further details or have specific requests, please let me know!"

**Expected (SMS‑ready):**
Standard check‑in: 3–4 PM.

**Outcome:** Expected - very minimal refactor

---
