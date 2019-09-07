# starline_api-ha
Starline device tracker for Home Assistant through offical API.
Based on official Starline API samples.

## WARNING
This integration may be unsecure. You can use it, but it's at your own risk.

## Features
Exposes all your Starline devices with GPS coordinates.

## Obtaining App ID and Secret
1. Go to https://my.starline.ru.
2. Select "Developer". If there is no such button - change language to "Russian". 
3. Authorize.
4. Register custom application. 
   In the description write, that you want to integrate your starline device into Home Assistant smart home system.
   Also you may write that you will use it with this integration only for tracking your devices.
   If your reqest will be accepted, you'll receive App ID and App Secret, needed to work with this integration.
5. I don't give any guarantees that Starline will accept your request. So if your request is rejected, you can try https://github.com/Cheaterdev/starline-ha. It works through https://starline-online.ru parsing.

## Setup
Place "starline_api" folder in **/custom_components** folder
	
```yaml
# configuration.yaml

device_tracker:
  - platform: starline_api
    scan_interval: 00:02:00
    username: !USERNAME!
    password: !PASSWORD!
    app_id: !APP_ID!
    app_secret: !APP_SECRET!
```

Configuration variables:
- **username** (*Required*): Your Starline username
- **password** (*Required*): Your Starline password
- **scan_interval** (*Optional*): Time to refresh data. Currently there is a limit for 1000 calls per day. Best option is 2 minutes or more.
- **app_id** (*Required*): Your Application ID
- **app_secret** (*Required*): Your Application Secret

# Device naming
 - starline_**IMEI**
 
## Disclaimer
This software is supplied "AS IS" without any warranties and support.
