# ContestFit server

ContestFit의 공모전과 자격 조건을 MySQL에 저장하고 REST API로 제공하는 Spring Boot 서버입니다.

## 현재 제공 API

- `GET /api/contests` - 공모전 목록과 조건 조회
- `GET /api/contests/{id}` - 한 공모전 상세 조회
- `POST /api/contests` - 공모전과 자격 조건 등록

`POST`는 현재 로컬 개발용입니다. 로그인과 운영 권한 관리는 아직 구현하지 않았습니다.

## DB 준비

MySQL에서 데이터베이스와 로컬 개발 계정을 만듭니다. 비밀번호는 팀에서 별도로 정하고 Git에 커밋하지 않습니다.

```sql
CREATE DATABASE contestfit CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
CREATE USER 'contestfit_app'@'localhost' IDENTIFIED BY 'change-this-local-password';
GRANT ALL PRIVILEGES ON contestfit.* TO 'contestfit_app'@'localhost';
FLUSH PRIVILEGES;
```

환경변수 예시:

```powershell
$env:DB_URL='jdbc:mysql://localhost:3306/contestfit?serverTimezone=Asia/Seoul&characterEncoding=utf8'
$env:DB_USERNAME='contestfit_app'
$env:DB_PASSWORD='change-this-local-password'
```

## 실행

JDK 21 이상과 MySQL이 필요합니다.

```powershell
cd server
mvn spring-boot:run
```

서버가 실행되면 `http://localhost:8080/api/contests`에서 목록을 확인합니다. 시작 시 Flyway가 `db/migration/V1__create_contestfit_schema.sql`을 적용해 테이블을 만듭니다.

## 검증

```powershell
cd server
mvn test
```
