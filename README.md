# Profile-Guided Deposition

This repository shows how deposition profiles are added to a [CESNET Invenio](https://nrp-cz.github.io/docs/) repository with the [oarepo-pgd](https://github.com/sb-ncbr/oarepo-pgd) plugin. It accompanies the NRP output D5.1.3, "Profile-guided deposition: repository implementation guide".

A deposition profile says which files a dataset should contain, for example at least one interview recording and optionally a transcript. Depositors select a profile, upload files and confirm what each file is. The repository counts the files against the profile and blocks publication until the required files are there. Readers can then filter datasets by profile and by file type, and see what each file is on the record page.

## History

Each step is marked by a tag, and the difference between neighbouring tags shows one step:

| Tag | Step |
|---|---|
| `d5.1.3-baseline` | A repository generated with the standard CESNET Invenio tools ([nrp-app-copier](https://github.com/oarepo/nrp-app-copier) and [nrp-model-copier](https://github.com/oarepo/nrp-model-copier)) on `oarepo-app` 8, with a `datasets` model, the stock Invenio logo, Czech as a second interface language and locked dependencies. |
| `d5.1.3-plugin` | oarepo-pgd 0.4.1 installed and enabled on the `datasets` model, with the deposit form connected, the file meanings shown on the record page and the recorded- and transcribed-interview profiles. |
| `d5.1.3-catch-all` | A general-dataset profile for diverse material. |
| `d5.1.3-cryo-em` | A cryo-EM map profile modelled on the EMDB deposition rules. |
| `d5.1.3-molecular-dynamics` | A GROMACS profile with file types adapted from the [BioSim CZ architecture](https://biosimcz-architecture.biodata.ceitec.cz/). |

The steps after `d5.1.3-plugin` add only configuration files. The `m5.1.2` tag marks the earlier version shown in M5.1.2, "Profile-guided deposition: concept and demonstration".

## Configuration

Profiles and file types are YAML files in `models/datasets/config/`:

- `semantic-types/` defines the file types, for example "Interview transcript".
- `profiles/` contains one file per profile with its requirements.

Texts are given in English and Czech. The format is described in the [oarepo-pgd configuration reference](https://github.com/sb-ncbr/oarepo-pgd/blob/v0.4.1/docs/configuration.md). The configuration is checked at startup, so a mistake in a YAML file stops the repository with a message naming the file. After changing the configuration, restart the web and worker processes.

## Installation

Install and run it like any CESNET Invenio repository, see the [CESNET Invenio documentation](https://nrp-cz.github.io/docs/installation/run_instance):

```sh
./run.sh install
./run.sh services setup -N
./run.sh run
```

`./run.sh run` serves the repository over HTTPS with a development certificate in `docker/`. The repository installer creates it for a new repository, but a clone has none, so create it once before the first run:

```sh
openssl req -x509 -newkey rsa:4096 -nodes -out docker/development.crt -keyout docker/development.key \
    -days 3650 -subj "/C=CH/ST=./L=./O=./OU=./CN=localhost/emailAddress=."
```

After pulling new commits, run `./run.sh install` again.

## Smoke test

With the services running, `tests/check_profiles.py` checks the configuration API, saving an incomplete draft and publication through a publish request:

```sh
set -a; source variables; set +a
.venv/bin/python tests/check_profiles.py
```

## Licence

MIT, see [LICENSE](LICENSE). The OARepo and Invenio packages installed by the repository have their own licences.

## Acknowledgements

![Co-funded by the European Union and the Ministry of Education, Youth and Sports of the Czech Republic](docs/funding.png)

This work is supported by the project [National Repository Platform for Research Data](https://www.eosc.cz/en/projects/national-repository-platform-for-research-data-nrp/national-repository-platform) no. CZ.02.01.01/00/23_014/0008787.
