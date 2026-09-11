from flask import Flask, request, abort
import requests
import logging

class Middleware():
    def validateAccessToken(token):
        # Removed 2026-09-11: was logging the client-provided token in
        # plaintext ("logging.info(token)").
        try:
            # Fixed 2026-09-11: was 'http://homeassistant.local:8123/api/'.
            # This validates a token the *client/dashboard* sends in, not
            # this add-on's own token -- so the Authorization header still
            # carries the caller's token unchanged. Only the transport URL
            # moves to the Supervisor proxy, which forwards to Core.
            url = "http://supervisor/core/api/"
            headers = {
                "Content-Type": "application/x-www-form-urlencoded",
                "Authorization": str(token)
            }

            response = requests.get(url, headers=headers, timeout=(3, 5))

            if response.status_code == 200:
                return True

            else:
                return False

        except Exception as e:
            return {"Faild to validate access token": str(e)}, 401
