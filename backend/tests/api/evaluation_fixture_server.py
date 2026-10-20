"""Isolated localhost browser-test server. Never loads or writes production judgments."""
from pathlib import Path
import uuid
import uvicorn
from backend.api.config import ROOT
from backend.api.main import create_app
from backend.tests.api.conftest import make_resources


def main():
    directory=ROOT/'var'/('evaluation-browser-fixture-'+uuid.uuid4().hex)
    directory.mkdir(parents=True)
    resources=make_resources(directory)
    settings=resources.settings.model_copy(update={'evaluation_enabled':True,'evaluation_mutations_enabled':True,
        'evaluation_db_path':directory/'evaluation.sqlite',
        'cors_origins':['http://127.0.0.1:3002','http://localhost:3002']})
    uvicorn.run(create_app(settings,lambda _:resources),host='127.0.0.1',port=8001,access_log=False)


if __name__=='__main__':main()
