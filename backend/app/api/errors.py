from fastapi import HTTPException


def bad_request(message: str) -> HTTPException:
    return HTTPException(status_code=400, detail={"code": "bad_request", "message": message})


def not_found(resource: str) -> HTTPException:
    return HTTPException(status_code=404, detail={"code": "not_found", "message": f"{resource} not found"})


def conflict(message: str) -> HTTPException:
    return HTTPException(status_code=409, detail={"code": "conflict", "message": message})
