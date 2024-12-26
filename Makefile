.ONESHELL:
.PHONY: test
.PHONY: run_coverage
.PHONY: report_coverage
.PHONY: development-diff-cover
.PHONY: docker
.PHONY: install
.PHONY: uninstall
.PHONY: clean
.PHONY: build

test:
	coverage run -m nose \
 	--exclude-dir="test/connector" \
 	--exclude-dir="test/debug" \
 	--exclude-dir="test/mock" \
 	--exclude-dir="test/hummingbot/connector/gateway/amm" \
 	--exclude-dir="test/hummingbot/connector/exchange/coinbase_pro" \
 	--exclude-dir="test/hummingbot/connector/exchange/hitbtc" \
 	--exclude-dir="test/hummingbot/connector/exchange/foxbit" \
 	--exclude-dir="test/hummingbot/connector/gateway/clob_spot/data_sources/dexalot" \
 	--exclude-dir="test/hummingbot/strategy/amm_arb" \
 	--exclude-dir="test/hummingbot/core/gateway" \
 	--exclude-dir="test/hummingbot/strategy/amm_v3_lp"

run_coverage: test
	coverage report
	coverage html

report_coverage:
	coverage report
	coverage html

development-diff-cover:
	coverage xml
	diff-cover --compare-branch=origin/development coverage.xml

docker:
	git clean -xdf && make clean && docker build  --platform linux/amd64 -t rakd/hummingbot${TAG} -f Dockerfile .
	docker tag 	rakd/hummingbot${TAG} ghcr.io/rakd/hummingbot${TAG}


dockerpush: docker
	docker push rakd/hummingbot
	
dockerpush2: docker
	echo $CR_PAT | docker login ghcr.io -u $GUSERNAME --password-stdin
	docker push ghcr.io/rakd/hummingbot${TAG}

clean:
	./clean

install:
	./install

uninstall:
	./uninstall

build:
	./compile
