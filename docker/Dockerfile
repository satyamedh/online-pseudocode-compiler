FROM gcc:latest
LABEL authors="Satyamedh"

# git clone https://github.com/satyamedh/CIE-Pseudocode-compiler
WORKDIR /usr/src/CIE-Pseudocode-compiler
RUN git clone https://github.com/satyamedh/CIE-Pseudocode-compiler .

# copy the source code to the container
COPY . .

ENTRYPOINT ["/usr/bin/python3", "main.py", "code.psc", "-rd"]
