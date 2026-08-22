# ── IAM: SageMaker 학습 실행 역할 ───────────────────────────────
data "aws_iam_policy_document" "sagemaker_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["sagemaker.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "sagemaker_execution" {
  name               = "lumina-sagemaker-execution-role"
  assume_role_policy = data.aws_iam_policy_document.sagemaker_assume.json
}

resource "aws_iam_role_policy" "sagemaker_execution_policy" {
  name = "sagemaker-training-access"
  role = aws_iam_role.sagemaker_execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["s3:GetObject", "s3:PutObject", "s3:ListBucket"]
        Resource = [aws_s3_bucket.ml_artifacts.arn, "${aws_s3_bucket.ml_artifacts.arn}/*"]
      },
      {
        Effect   = "Allow"
        Action   = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents", "logs:DescribeLogStreams"]
        Resource = "arn:aws:logs:${var.region}:${var.account_id}:log-group:/aws/sagemaker/*"
      },
      {
        Effect   = "Allow"
        Action   = ["cloudwatch:PutMetricData"]
        Resource = "*"
      },
    ]
  })
}

# ── IAM: Lambda 실행 역할 (기본 실행 + 학습 Job 시작) ────────────
data "aws_iam_policy_document" "lambda_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "lambda_quant_retrain" {
  name               = "lumina-lambda-quant-retrain-role"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume.json
}

resource "aws_iam_role_policy_attachment" "lambda_quant_retrain_basic" {
  role       = aws_iam_role.lambda_quant_retrain.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy" "lambda_quant_retrain_policy" {
  name = "start-sagemaker-training"
  role = aws_iam_role.lambda_quant_retrain.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["sagemaker:CreateTrainingJob"]
        Resource = "arn:aws:sagemaker:${var.region}:${var.account_id}:training-job/lumina-quant-retrain-*"
      },
      {
        Effect   = "Allow"
        Action   = ["iam:PassRole"]
        Resource = [aws_iam_role.sagemaker_execution.arn]
      },
    ]
  })
}

# ── Lambda: 학습 Job 시작 트리거 ────────────────────────────────
data "archive_file" "quant_retrain_trigger" {
  type        = "zip"
  output_path = "${path.module}/.terraform/tmp/lambda_quant_retrain.zip"

  source {
    filename = "lambda_function.py"
    content  = <<-PYTHON
      import os
      import time

      import boto3

      sagemaker = boto3.client("sagemaker")


      def handler(event, context):
          job_name = f"lumina-quant-retrain-{int(time.time())}"
          bucket = os.environ["ML_BUCKET"]

          sagemaker.create_training_job(
              TrainingJobName=job_name,
              AlgorithmSpecification={
                  "TrainingImage": os.environ["TRAINING_IMAGE"],
                  "TrainingInputMode": "File",
              },
              HyperParameters={
                  "sagemaker_program": "train.py",
                  "sagemaker_submit_directory": f"s3://{bucket}/code/quant_train_source.tar.gz",
              },
              RoleArn=os.environ["SAGEMAKER_ROLE_ARN"],
              OutputDataConfig={"S3OutputPath": f"s3://{bucket}/output/"},
              ResourceConfig={
                  "InstanceType": "ml.m5.large",
                  "InstanceCount": 1,
                  "VolumeSizeInGB": 10,
              },
              StoppingCondition={
                  "MaxRuntimeInSeconds": 3600,
                  "MaxWaitTimeInSeconds": 7200,
              },
              EnableManagedSpotTraining=True,
              Environment={"SCORES_BUCKET": bucket},
          )
          return {"job_name": job_name}
    PYTHON
  }
}

resource "aws_lambda_function" "quant_retrain_trigger" {
  function_name    = "lumina-quant-retrain-trigger"
  role             = aws_iam_role.lambda_quant_retrain.arn
  handler          = "lambda_function.handler"
  runtime          = "python3.12"
  filename         = data.archive_file.quant_retrain_trigger.output_path
  source_code_hash = data.archive_file.quant_retrain_trigger.output_base64sha256
  memory_size      = 128
  timeout          = 30

  environment {
    variables = {
      ML_BUCKET          = aws_s3_bucket.ml_artifacts.bucket
      SAGEMAKER_ROLE_ARN = aws_iam_role.sagemaker_execution.arn
      TRAINING_IMAGE     = var.sagemaker_sklearn_image
    }
  }

  depends_on = [null_resource.quant_train_package]
}

resource "aws_cloudwatch_log_group" "lambda_quant_retrain" {
  name              = "/aws/lambda/lumina-quant-retrain-trigger"
  retention_in_days = 14
}

# ── EventBridge Scheduler: 일 1회 (01:00 UTC = 한국시간 10:00) ──
data "aws_iam_policy_document" "scheduler_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["scheduler.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "quant_scheduler" {
  name               = "lumina-quant-scheduler-role"
  assume_role_policy = data.aws_iam_policy_document.scheduler_assume.json
}

resource "aws_iam_role_policy" "quant_scheduler_invoke" {
  name = "invoke-quant-retrain-lambda"
  role = aws_iam_role.quant_scheduler.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["lambda:InvokeFunction"]
      Resource = [aws_lambda_function.quant_retrain_trigger.arn]
    }]
  })
}

resource "aws_scheduler_schedule" "daily_quant_retrain" {
  name       = "lumina-daily-quant-retrain"
  group_name = "default"

  flexible_time_window { mode = "OFF" }
  schedule_expression = "cron(0 1 * * ? *)"

  target {
    arn      = aws_lambda_function.quant_retrain_trigger.arn
    role_arn = aws_iam_role.quant_scheduler.arn
  }
}

resource "aws_lambda_permission" "eventbridge_quant_retrain" {
  statement_id  = "AllowEventBridgeSchedulerInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.quant_retrain_trigger.function_name
  principal     = "scheduler.amazonaws.com"
  source_arn    = aws_scheduler_schedule.daily_quant_retrain.arn
}
