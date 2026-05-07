
|Feature|Poetry (Python)|Gradle (Java)|
|---|---|---|
|Config file|`pyproject.toml`[python-poetry](https://python-poetry.org/docs/)​|`build.gradle`[redhat](https://www.redhat.com/en/blog/manage-java-dependencies-maven)​|
|Lockfile|`poetry.lock`|`gradle.lockfile`|
|Install deps|`poetry install`|`./gradlew dependencies`|
|Run tests|`poetry run pytest`|`./gradlew test`|
|Build/publish|`poetry build`|`./gradlew build publish`[hackernoon](https://hackernoon.com/dependency-management-in-microservice-architecture-creating-your-own-parent-pom)​|
