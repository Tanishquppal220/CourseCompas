Table Programs {
  ProgramID int [pk, increment]
  ProgramCode varchar(50)
  ProgramName varchar(255)
  AdmissionYear int
  DurationYears int
}

Table Courses {
  CourseCode varchar(20) [pk]
  CourseTitle varchar(255)
  L int
  T int
  P int
  Credit decimal(3,1)
  ContactHours decimal(4,1)
  CourseType varchar(10)
  CourseNature varchar(10)
}

Table Terms {
  TermID int [pk, increment]
  ProgramID int
  TermNumber int
  TermPath varchar(100)
}

Table Term_Curriculum {
  CurriculumID int [pk, increment]
  TermID int
  CourseCode varchar(20) [null]
  PlaceholderName varchar(100) [null]
}

Table Elective_Baskets {
  BasketID int [pk, increment]
  BasketName varchar(100)
  CourseCode varchar(20)
  ElectiveArea varchar(100) [null]
}

Table Course_Prerequisites {
  CourseCode varchar(20)
  PrereqCode varchar(20)
}

Ref: Terms.ProgramID > Programs.ProgramID
Ref: Term_Curriculum.TermID > Terms.TermID
Ref: Term_Curriculum.CourseCode > Courses.CourseCode
Ref: Elective_Baskets.CourseCode > Courses.CourseCode
Ref: Course_Prerequisites.CourseCode > Courses.CourseCode
Ref: Course_Prerequisites.PrereqCode > Courses.CourseCode