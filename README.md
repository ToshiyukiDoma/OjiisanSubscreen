# Ojii-san Subscreen
## Wanna try older sound voltex games with a touch screen monitor that has no subscreen support?

<img width="640" height="720" alt="preview" src="https://github.com/user-attachments/assets/4addd6b5-72b0-439b-9113-51a3ac098b1b" />

## Features:
- You can hide the system buttons which are the Test, Service, and Coin buttons.
- Multiple Custom Backgrounds (Image and/or Video are supported)
- Interchangeable backgrounds while the app is running
- Running on Virtual Joypad baked into the application
- Customizable buttons. You can also relocate them anywhere on the screen by editing the config.json
- Concentration Mode: The UI elements will disappear except for the background and will dim depending on your timeout and dim preference.

## Usage:
- Set your sound voltex to borderless fullscreen
- Open and modify config.json to
    - Configure your background directory (Set by default at backgrounds)
    - Set which monitor it will open to (Set by default at 1)
- Run the Boomer Subscreen first
- Configure the buttons to Spice2x
- Run the game you're playing
- Enjoy gaem
- Nice one

## Issues:
- It will not work with konasute
- It is a requirement to play the game on borderless fullscreen because it's a separate application, not a plugin


## DIY Build
```
pip install -r requirements.txt
pyinstaller --noconsole --onefile --name "OjiisanSubscreen" --icon="icon.ico" --collect-all vgamepad OjiisanSubscreen.py
```


##
###### - Made with ChatGPT and Google Gemini </br> - Button graphics were made from scratch

#### Uhe~
