.PHONY: doc docs test tests clean

doc docs:
	make -C doc html

test tests:
	pytest

clean:
	make -C doc clean
	find . | grep -E "(__pycache__|\.pyc|\.pyo$\)" | xargs rm -rf
