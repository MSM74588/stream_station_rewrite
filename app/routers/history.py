from fastapi import APIRouter, Query, HTTPException
from sqlmodel import Session, select
from typing import List, Optional, Union
from app.database import engine
from app.models import History

router = APIRouter()

@router.get("/history", response_model=List[History], summary="Get playback history")
def get_history(
    limit: Union[str, int] = Query(
        default="100",
        description=(
            "Limit the number of history items returned.\n\n"
            "- Set to `all` to return all entries.\n"
            "- Set to a number (e.g. `50`) to return the latest N entries.\n"
            "- Defaults to `100`."
        ),
        examples={
            "default": {"summary": "Default (latest 100)", "value": "100"},
            "all": {"summary": "All entries", "value": "all"},
            "custom": {"summary": "Custom number of entries", "value": "50"}
        } # type: ignore
    )
):
    try:
        with Session(engine) as session:
            statement = select(History).order_by(History.time.desc())

            if isinstance(limit, str):
                if limit.lower() == "all":
                    results = session.exec(statement).all()
                elif limit.isdigit():
                    results = session.exec(statement.limit(int(limit))).all()
                else:
                    raise HTTPException(status_code=400, detail="Invalid limit parameter. Use 'all' or a number.")
            elif isinstance(limit, int):
                results = session.exec(statement.limit(limit)).all()
            else:
                raise HTTPException(status_code=400, detail="Invalid limit parameter type.")

            return results

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch history: {str(e)}")
