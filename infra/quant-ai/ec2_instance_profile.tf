# ─────────────────────────────────────────────────────────────
# fund-web EC2에 붙일 IAM 인스턴스 프로파일 — 현재 이 인스턴스엔 아무 IAM 프로파일도
# 없어서(aws ec2 describe-instances 확인) 앱이 AWS API를 전혀 호출할 수 없다.
# 여기서는 역할/프로파일만 만들고, 실제 EC2에 "붙이는" 작업은 이 인스턴스를
# terraform import하지 않고 apply 이후 별도 CLI로 한다 (운영 서버를 통째로
# terraform 관리 대상으로 가져오면 의도치 않은 drift 수정이 발생할 위험이 있어서).
#
#   aws ec2 associate-iam-instance-profile \
#     --instance-id ${var.fund_web_instance_id} \
#     --iam-instance-profile Name=lumina-fund-web-profile \
#     --region ${var.region}
# ─────────────────────────────────────────────────────────────

data "aws_iam_policy_document" "ec2_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "fund_web" {
  name               = "lumina-fund-web-role"
  assume_role_policy = data.aws_iam_policy_document.ec2_assume.json
}

resource "aws_iam_role_policy" "fund_web_ai" {
  name = "quant-ai-signals"
  role = aws_iam_role.fund_web.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["comprehend:DetectSentiment", "comprehend:BatchDetectSentiment"]
        Resource = "*" # Comprehend는 리소스 레벨 권한을 지원하지 않음
      },
      {
        Effect   = "Allow"
        Action   = ["s3:GetObject"]
        Resource = "${aws_s3_bucket.ml_artifacts.arn}/latest/scores.json"
      },
    ]
  })
}

resource "aws_iam_instance_profile" "fund_web" {
  name = "lumina-fund-web-profile"
  role = aws_iam_role.fund_web.name
}
