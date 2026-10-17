import os
import sys

# Ensure parent directory is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
try:
    import sentence_transformers
except Exception:
    pass

from typing import List, Optional, Dict, Any
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from database import SessionLocal, init_db, Workspace, Paper, Query
from graph import run_orion

# Ensure database tables exist
init_db()

app = FastAPI(title="ORION API", version="1.0")

# Enable CORS for all origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Pydantic Schemas
class CreateWorkspaceRequest(BaseModel):
    name: str


class ResearchRequest(BaseModel):
    topic: str
    workspace_id: int
    devil_advocate: bool = False


# Endpoints
@app.get("/")
def root():
    return {"status": "ORION is running", "version": "1.0"}


@app.get("/health")
def health():
    return {"status": "ok", "database": "connected"}


@app.post("/workspace/create")
def create_workspace(req: CreateWorkspaceRequest):
    db = SessionLocal()
    try:
        ws = Workspace(name=req.name)
        db.add(ws)
        db.commit()
        db.refresh(ws)
        return {"workspace_id": ws.id, "name": ws.name}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


@app.get("/workspace/{workspace_id}/papers")
def get_workspace_papers(workspace_id: int):
    db = SessionLocal()
    try:
        papers = db.query(Paper).filter(Paper.workspace_id == workspace_id).all()
        paper_list = []
        for p in papers:
            paper_list.append({
                "id": p.id,
                "workspace_id": p.workspace_id,
                "arxiv_id": p.arxiv_id,
                "title": p.title,
                "authors": p.authors,
                "abstract": p.abstract,
                "year": p.year,
                "venue": p.venue,
                "citations": p.citations,
                "final_score": p.final_score,
                "pdf_url": p.pdf_url,
                "ingested": p.ingested,
                "ingested_at": p.ingested_at.isoformat() if p.ingested_at else None,
            })
        return {"papers": paper_list}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


@app.post("/research")
def research_endpoint(req: ResearchRequest):
    print(f"Incoming topic: '{req.topic}' | Final agent used: Critic/Synthesizer")
    try:
        result = run_orion(
            topic=req.topic,
            workspace_id=req.workspace_id,
            devil_advocate=req.devil_advocate,
        )

        synth = result.get("synthesis_output", {})
        answer = result.get("final_answer") or synth.get("answer", "")
        confidence = float(synth.get("confidence", 0.0) or 0.0)
        stance_summary = synth.get("stance_summary", {})
        evidence_grades = synth.get("evidence_grades", {})
        devil_advocate_res = synth.get("devil_advocate")
        replan_count = result.get("replan_count", 0)
        reasoning_log = result.get("reasoning_log", [])
        chunks_used = synth.get("chunks_used", 0)
        web_sources_used = synth.get("web_sources_used", 0)

        # Extract papers and sub_questions for frontend use
        research_results = result.get("research_results", {})
        papers = research_results.get("arxiv_results", [])
        plan = result.get("plan", {})
        sub_questions = plan.get("sub_questions", [])

        # Save query to SQLite queries table
        db = SessionLocal()
        try:
            db_query = Query(
                workspace_id=req.workspace_id,
                question=req.topic,
                answer=answer,
                confidence_score=confidence,
            )
            db.add(db_query)
            ws = db.query(Workspace).filter(Workspace.id == req.workspace_id).first()
            if ws:
                ws.query_count = (ws.query_count or 0) + 1
            db.commit()
        except Exception as db_err:
            print(f"[Warning] Failed to save query to database: {db_err}")
            db.rollback()
        finally:
            db.close()

        return {
            "answer": answer,
            "confidence": confidence,
            "confidence_score": confidence,  # alias for clients
            "stance_summary": stance_summary,
            "evidence_grades": evidence_grades,
            "devil_advocate": devil_advocate_res,
            "replan_count": replan_count,
            "reasoning_log": reasoning_log,
            "chunks_used": chunks_used,
            "web_sources_used": web_sources_used,
            "papers": papers,
            "sub_questions": sub_questions,
        }
    except Exception as e:
        print(f"[Error] Research endpoint failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/workspace/{workspace_id}/metrics")
def get_workspace_metrics(workspace_id: int):
    db = SessionLocal()
    try:
        queries = db.query(Query).filter(Query.workspace_id == workspace_id).all()
        total_queries = len(queries)
        if total_queries > 0:
            conf_scores = [q.confidence_score for q in queries if q.confidence_score is not None]
            avg_confidence = float(sum(conf_scores) / len(conf_scores)) if conf_scores else 0.0
        else:
            avg_confidence = 0.0

        papers_ingested = db.query(Paper).filter(
            Paper.workspace_id == workspace_id,
            Paper.ingested == True,
        ).count()

        return {
            "total_queries": total_queries,
            "avg_confidence": round(avg_confidence, 4),
            "papers_ingested": papers_ingested,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


@app.delete("/workspace/{workspace_id}/clear")
def clear_workspace(workspace_id: int):
    db = SessionLocal()
    try:
        db.query(Query).filter(Query.workspace_id == workspace_id).delete()
        db.commit()
        return {"message": "Workspace cleared"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
