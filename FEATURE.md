# Requirements I am thinking about to implements

- [x] in other to improve application performance create a cron-job that fetches all the variation_code and the required information and cache them locally for the users
  - This can be very useful when trying to work on our recommendation feature.
- [x] Ask for transaction pin on for first time transfers
- [x] How do we handle a failed data purchase when the money has already been taken from the customer
  - Raise a dispute
  - Get your money back immediately
- [x] Can save beneficiaries
- [x] Can schedule bill payments
- [x] Has an option to list and cancel scheduled payments
- [x] Has a way to also communicate that the payment could not go through because of insufficient funds
- [x] MAXIMUM TRANSACTION AMOUNT SECURITY
- [x] Can schedule bill Notifications as sms or as gifts
- [x] Add auditing, user, admin, and agent
- [x] Can dynamically generate reports for their customer
- [x] A system that can calculate in real time the cost of every request a user makes and let our admin know if that request made us profit or made us a loss. Use the session ID to group sessions to know if the session was profitable or not. Also, use a similar approach to how LangSmith uses to aggregate tracing to a project to achieve this tracking
- [x] When tracking user payment, I want to be able to know if the person paid with a card and did he use a re saved card
- [x] Ability to get users feedback
- [x] Reward gamification just like the slot machine/labubu approach reference link
  - <https://www.youtube.com/watch?v=_FUv6Eb7FuM&t=1s>[!LABUBU-LINK]
  - I think we can gamify it such that users can create an army of “dera”and in each month if their army buys as much as the user thinks, the user gets to keep a gift, and the gift would be computed as the average of what must of their army has purchased for that month.

Gamification of a bills payment chatbot

- [x] For utility bills like light, we should allow the user to generate a receipt on our website
  - Sharing of payment link to let someone else pay for ones bill maybe data
  - Check if our balance on VTPASS is below the threshold; if it is, send me a notification to make payment into our VTPASS account immediately. Check for this every 10mins

- [x] Bored mode
  - This allows users to play with IderaAI and ask it to recommend movies for them to watch

- [x] Gift cards and pay-for-me feature where the user receive a sharable link that there sponsor can then go ahead and pay with

## Other implementations

- [x] Implement Key pass for admin signin

## Research

- [x] Study how labubu did there market to get users
- [x] Study how wee chat payment took over alipay in China
- [x] Study how Qwen AI chat bot is trying to acquire users by give free boba tea
- [x] Study how luckin took over the coffee market in china
