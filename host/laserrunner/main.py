import uvicorn

def main():
    print("==================================================")
    print("   LaserRunner Studio OS (Klipper-Style Laser)   ")
    print("==================================================")
    print("Web Arayuzu: http://localhost:8080")
    print("Raspberry Pi: http://<raspberry-pi-ip>:8080")
    uvicorn.run("laserrunner.server.app:app", host="0.0.0.0", port=8080, reload=False)

if __name__ == "__main__":
    main()
