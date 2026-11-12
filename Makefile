.PHONY: all test compile lint format deploy-local deploy-sepolia oracle-weather oracle-satellite oracle-soil oracle-all experiments

all: compile test

test:
	npm run test

compile:
	npm run compile

lint:
	npm run lint

format:
	npm run format

deploy-local:
	npm run deploy:local

deploy-sepolia:
	npm run deploy:sepolia

oracle-weather:
	npm run oracle:weather

oracle-satellite:
	npm run oracle:satellite

oracle-soil:
	npm run oracle:soil

oracle-all:
	npm run oracle:all

experiments:
	npm run experiments
