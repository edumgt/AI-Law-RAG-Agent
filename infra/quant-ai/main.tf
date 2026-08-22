# ─────────────────────────────────────────────────────────────
# 퀀트 AI 리소스 (SageMaker 배치 재학습 + Comprehend 감성분석) — 독립 스택
#
# 실제 운영 시스템은 EC2 단일 서버(fund-web, ap-northeast-2)에서 docker compose로
# 떠 있고, terraform/(ECS+RDS+ALB+CloudFront)는 한 번도 apply된 적 없는 별도 설계도라
# 여기서 재사용하지 않는다. 이 스택은 완전히 독립적이며 다음만 만든다:
#   - S3 버킷 (SageMaker 학습 코드 + scores.json 산출물)
#   - SageMaker 학습 실행 역할
#   - 학습 Job을 매일 트리거하는 Lambda + EventBridge Scheduler
#   - EC2(fund-web)에 붙일 IAM 인스턴스 프로파일 (Comprehend + S3 GetObject)
#
# EC2 인스턴스 자체는 terraform 관리 대상이 아니므로(기존 운영 서버를 import하면
# 의도치 않은 변경이 생길 위험이 있음), 인스턴스 프로파일 "연결"은 apply 이후
# 별도의 `aws ec2 associate-iam-instance-profile` 명령으로 수행한다.
# ─────────────────────────────────────────────────────────────

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.0"
    }
    null = {
      source  = "hashicorp/null"
      version = "~> 3.2"
    }
  }
}

provider "aws" {
  region = var.region
}
