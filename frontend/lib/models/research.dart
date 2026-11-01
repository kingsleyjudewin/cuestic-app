class FacultyProfile {
  final int id;
  final int userId;
  final String fullName;
  final String department;
  final String? designation;
  final String? specialization;
  final String? researchInterests;
  final String? bio;
  final String? phoneNumber;
  final String? profileImageUrl;
  final bool mustChangePassword;

  FacultyProfile({
    required this.id,
    required this.userId,
    required this.fullName,
    required this.department,
    this.designation,
    this.specialization,
    this.researchInterests,
    this.bio,
    this.phoneNumber,
    this.profileImageUrl,
    required this.mustChangePassword,
  });

  factory FacultyProfile.fromJson(Map<String, dynamic> json) {
    return FacultyProfile(
      id: json['id'] as int? ?? 0,
      userId: json['user_id'] as int? ?? 0,
      fullName: json['full_name'] as String? ?? 'Faculty Coordinator',
      department: json['department'] as String? ?? 'Electronics and Communication Engineering',
      designation: json['designation'] as String?,
      specialization: json['specialization'] as String?,
      researchInterests: json['research_interests'] as String?,
      bio: json['bio'] as String?,
      phoneNumber: json['phone_number'] as String?,
      profileImageUrl: json['profile_image_url'] as String?,
      mustChangePassword: json['must_change_password'] as bool? ?? false,
    );
  }
}

class ResearchStudentProfile {
  final int id;
  final int userId;
  final int? memberId;
  final String fullName;
  final String registrationNumber;
  final String email;
  final String department;
  final String programme;
  final String semester;
  final String? phoneNumber;
  final String? profileImageUrl;
  final bool mustChangePassword;
  final List<dynamic>? teams;
  final List<dynamic>? projects;
  final int tasksCount;
  final int completedTasksCount;

  ResearchStudentProfile({
    required this.id,
    required this.userId,
    this.memberId,
    required this.fullName,
    required this.registrationNumber,
    required this.email,
    required this.department,
    required this.programme,
    required this.semester,
    this.phoneNumber,
    this.profileImageUrl,
    required this.mustChangePassword,
    this.teams,
    this.projects,
    this.tasksCount = 0,
    this.completedTasksCount = 0,
  });

  factory ResearchStudentProfile.fromJson(Map<String, dynamic> json) {
    return ResearchStudentProfile(
      id: json['id'] as int? ?? 0,
      userId: json['user_id'] as int? ?? 0,
      memberId: json['member_id'] as int?,
      fullName: json['full_name'] as String? ?? 'Student Researcher',
      registrationNumber: json['registration_number'] as String? ?? '',
      email: json['email'] as String? ?? '',
      department: json['department'] as String? ?? 'ECE',
      programme: json['programme'] as String? ?? 'B.Tech ECE',
      semester: json['semester'] as String? ?? 'Semester 5',
      phoneNumber: json['phone_number'] as String?,
      profileImageUrl: json['profile_image_url'] as String?,
      mustChangePassword: json['must_change_password'] as bool? ?? false,
      teams: json['teams'] as List<dynamic>?,
      projects: json['projects'] as List<dynamic>?,
      tasksCount: json['tasks_count'] as int? ?? 0,
      completedTasksCount: json['completed_tasks_count'] as int? ?? 0,
    );
  }
}

class ResearchTeam {
  final int id;
  final int facultyId;
  final String? facultyName;
  final String name;
  final String domain;
  final String? description;
  final String? objectives;
  final String? tagsJson;
  final int memberCount;
  final int projectCount;
  final List<Map<String, dynamic>> members;
  final List<Map<String, dynamic>> projects;

  ResearchTeam({
    required this.id,
    required this.facultyId,
    this.facultyName,
    required this.name,
    required this.domain,
    this.description,
    this.objectives,
    this.tagsJson,
    this.memberCount = 0,
    this.projectCount = 0,
    this.members = const [],
    this.projects = const [],
  });

  factory ResearchTeam.fromJson(Map<String, dynamic> json) {
    var rawMembers = json['members'] as List<dynamic>? ?? [];
    var rawProjects = json['projects'] as List<dynamic>? ?? [];
    return ResearchTeam(
      id: json['id'] as int? ?? 0,
      facultyId: json['faculty_id'] as int? ?? 0,
      facultyName: json['faculty_name'] as String?,
      name: json['name'] as String? ?? 'Unnamed Team',
      domain: json['domain'] as String? ?? '',
      description: json['description'] as String?,
      objectives: json['objectives'] as String?,
      tagsJson: json['tags_json'] as String?,
      memberCount: json['member_count'] as int? ?? rawMembers.length,
      projectCount: json['project_count'] as int? ?? rawProjects.length,
      members: rawMembers.map((e) => Map<String, dynamic>.from(e as Map)).toList(),
      projects: rawProjects.map((e) => Map<String, dynamic>.from(e as Map)).toList(),
    );
  }
}

class ResearchProject {
  final int id;
  final int teamId;
  final String? teamName;
  final int facultyId;
  final String? facultyName;
  final String title;
  final String? researchProblem;
  final String? objectives;
  final String? description;
  final String? startDate;
  final String? expectedCompletionDate;
  final String status;
  final bool isArchived;
  final List<Map<String, dynamic>> members;
  final List<ResearchMilestone> milestones;

  ResearchProject({
    required this.id,
    required this.teamId,
    this.teamName,
    required this.facultyId,
    this.facultyName,
    required this.title,
    this.researchProblem,
    this.objectives,
    this.description,
    this.startDate,
    this.expectedCompletionDate,
    required this.status,
    required this.isArchived,
    this.members = const [],
    this.milestones = const [],
  });

  factory ResearchProject.fromJson(Map<String, dynamic> json) {
    var rawMembers = json['members'] as List<dynamic>? ?? [];
    var rawMilestones = json['milestones'] as List<dynamic>? ?? [];
    return ResearchProject(
      id: json['id'] as int? ?? 0,
      teamId: json['team_id'] as int? ?? 0,
      teamName: json['team_name'] as String?,
      facultyId: json['faculty_id'] as int? ?? 0,
      facultyName: json['faculty_name'] as String?,
      title: json['title'] as String? ?? 'Untitled Project',
      researchProblem: json['research_problem'] as String?,
      objectives: json['objectives'] as String?,
      description: json['description'] as String?,
      startDate: json['start_date'] as String?,
      expectedCompletionDate: json['expected_completion_date'] as String?,
      status: json['status'] as String? ?? 'in_progress',
      isArchived: json['is_archived'] as bool? ?? false,
      members: rawMembers.map((e) => Map<String, dynamic>.from(e as Map)).toList(),
      milestones: rawMilestones.map((e) => ResearchMilestone.fromJson(Map<String, dynamic>.from(e as Map))).toList(),
    );
  }
}

class ResearchMilestone {
  final int id;
  final int projectId;
  final String title;
  final String? description;
  final String? targetCriteria;
  final String? startDate;
  final String? dueDate;
  final String priority;
  final String status;
  final int completionPercentage;
  final List<ResearchTask> tasks;

  ResearchMilestone({
    required this.id,
    required this.projectId,
    required this.title,
    this.description,
    this.targetCriteria,
    this.startDate,
    this.dueDate,
    required this.priority,
    required this.status,
    this.completionPercentage = 0,
    this.tasks = const [],
  });

  factory ResearchMilestone.fromJson(Map<String, dynamic> json) {
    var rawTasks = json['tasks'] as List<dynamic>? ?? [];
    return ResearchMilestone(
      id: json['id'] as int? ?? 0,
      projectId: json['project_id'] as int? ?? 0,
      title: json['title'] as String? ?? 'Milestone',
      description: json['description'] as String?,
      targetCriteria: json['target_criteria'] as String?,
      startDate: json['start_date'] as String?,
      dueDate: json['due_date'] as String?,
      priority: json['priority'] as String? ?? 'Medium',
      status: json['status'] as String? ?? 'in_progress',
      completionPercentage: json['completion_percentage'] as int? ?? 0,
      tasks: rawTasks.map((e) => ResearchTask.fromJson(Map<String, dynamic>.from(e as Map))).toList(),
    );
  }
}

class ResearchTask {
  final int id;
  final int? milestoneId;
  final String? milestoneTitle;
  final int projectId;
  final String? projectTitle;
  final String title;
  final String? instructions;
  final String? dueDate;
  final String priority;
  final String status;
  final int progressPercentage;
  final String? completionCriteria;
  final List<Map<String, dynamic>> assignees;

  ResearchTask({
    required this.id,
    this.milestoneId,
    this.milestoneTitle,
    required this.projectId,
    this.projectTitle,
    required this.title,
    this.instructions,
    this.dueDate,
    required this.priority,
    required this.status,
    this.progressPercentage = 0,
    this.completionCriteria,
    this.assignees = const [],
  });

  factory ResearchTask.fromJson(Map<String, dynamic> json) {
    var rawAssignees = json['assignees'] as List<dynamic>? ?? [];
    return ResearchTask(
      id: json['id'] as int? ?? 0,
      milestoneId: json['milestone_id'] as int?,
      milestoneTitle: json['milestone_title'] as String?,
      projectId: json['project_id'] as int? ?? 0,
      projectTitle: json['project_title'] as String?,
      title: json['title'] as String? ?? 'Task',
      instructions: json['instructions'] as String?,
      dueDate: json['due_date'] as String?,
      priority: json['priority'] as String? ?? 'Medium',
      status: json['status'] as String? ?? 'not_started',
      progressPercentage: json['progress_percentage'] as int? ?? 0,
      completionCriteria: json['completion_criteria'] as String?,
      assignees: rawAssignees.map((e) => Map<String, dynamic>.from(e as Map)).toList(),
    );
  }

  ResearchTask copyWith({
    int? id,
    int? milestoneId,
    String? milestoneTitle,
    int? projectId,
    String? projectTitle,
    String? title,
    String? instructions,
    String? dueDate,
    String? priority,
    String? status,
    int? progressPercentage,
    String? completionCriteria,
    List<Map<String, dynamic>>? assignees,
  }) {
    return ResearchTask(
      id: id ?? this.id,
      milestoneId: milestoneId ?? this.milestoneId,
      milestoneTitle: milestoneTitle ?? this.milestoneTitle,
      projectId: projectId ?? this.projectId,
      projectTitle: projectTitle ?? this.projectTitle,
      title: title ?? this.title,
      instructions: instructions ?? this.instructions,
      dueDate: dueDate ?? this.dueDate,
      priority: priority ?? this.priority,
      status: status ?? this.status,
      progressPercentage: progressPercentage ?? this.progressPercentage,
      completionCriteria: completionCriteria ?? this.completionCriteria,
      assignees: assignees ?? this.assignees,
    );
  }
}

class ResearchFeedbackMessage {
  final int id;
  final int threadId;
  final int? senderUserId;
  final String? senderName;
  final String senderRole;
  final String messageText;
  final String messageType;
  final String? actionDecision;
  final String? createdAt;
  final List<ResearchAttachment> attachments;

  ResearchFeedbackMessage({
    required this.id,
    required this.threadId,
    this.senderUserId,
    this.senderName,
    required this.senderRole,
    required this.messageText,
    required this.messageType,
    this.actionDecision,
    this.createdAt,
    this.attachments = const [],
  });

  factory ResearchFeedbackMessage.fromJson(Map<String, dynamic> json) {
    var rawAtts = json['attachments'] as List<dynamic>? ?? [];
    return ResearchFeedbackMessage(
      id: json['id'] as int? ?? 0,
      threadId: json['thread_id'] as int? ?? 0,
      senderUserId: json['sender_user_id'] as int?,
      senderName: json['sender_name'] as String?,
      senderRole: json['sender_role'] as String? ?? 'user',
      messageText: json['message_text'] as String? ?? '',
      messageType: json['message_type'] as String? ?? 'comment',
      actionDecision: json['action_decision'] as String?,
      createdAt: json['created_at'] as String?,
      attachments: rawAtts.map((e) => ResearchAttachment.fromJson(Map<String, dynamic>.from(e as Map))).toList(),
    );
  }
}

class ResearchAttachment {
  final int id;
  final String fileName;
  final String fileType;
  final int fileSize;
  final String storagePath;
  final String? description;
  final String? fileUrl;

  ResearchAttachment({
    required this.id,
    required this.fileName,
    required this.fileType,
    required this.fileSize,
    required this.storagePath,
    this.description,
    this.fileUrl,
  });

  factory ResearchAttachment.fromJson(Map<String, dynamic> json) {
    return ResearchAttachment(
      id: json['id'] as int? ?? 0,
      fileName: json['file_name'] as String? ?? 'File',
      fileType: json['file_type'] as String? ?? 'document',
      fileSize: json['file_size'] as int? ?? 0,
      storagePath: json['storage_path'] as String? ?? '',
      description: json['description'] as String?,
      fileUrl: json['file_url'] as String?,
    );
  }
}

class ResearchMeeting {
  final int id;
  final int facultyId;
  final String? facultyName;
  final int? teamId;
  final String? teamName;
  final String title;
  final String? agenda;
  final String? scheduledAt;
  final int durationMinutes;
  final String? locationOrLink;
  final String? meetingNotes;
  final String status;
  final List<Map<String, dynamic>> participants;

  ResearchMeeting({
    required this.id,
    required this.facultyId,
    this.facultyName,
    this.teamId,
    this.teamName,
    required this.title,
    this.agenda,
    this.scheduledAt,
    this.durationMinutes = 60,
    this.locationOrLink,
    this.meetingNotes,
    required this.status,
    this.participants = const [],
  });

  factory ResearchMeeting.fromJson(Map<String, dynamic> json) {
    var rawParts = json['participants'] as List<dynamic>? ?? [];
    return ResearchMeeting(
      id: json['id'] as int? ?? 0,
      facultyId: json['faculty_id'] as int? ?? 0,
      facultyName: json['faculty_name'] as String?,
      teamId: json['team_id'] as int?,
      teamName: json['team_name'] as String?,
      title: json['title'] as String? ?? 'Research Meeting',
      agenda: json['agenda'] as String?,
      scheduledAt: json['scheduled_at'] as String?,
      durationMinutes: json['duration_minutes'] as int? ?? 60,
      locationOrLink: json['location_or_link'] as String?,
      meetingNotes: json['meeting_notes'] as String?,
      status: json['status'] as String? ?? 'scheduled',
      participants: rawParts.map((e) => Map<String, dynamic>.from(e as Map)).toList(),
    );
  }
}

class ResearchNotification {
  final int id;
  final String title;
  final String body;
  final String notificationType;
  final int? referenceId;
  final String? referenceType;
  final bool isRead;
  final String? createdAt;

  ResearchNotification({
    required this.id,
    required this.title,
    required this.body,
    required this.notificationType,
    this.referenceId,
    this.referenceType,
    required this.isRead,
    this.createdAt,
  });

  factory ResearchNotification.fromJson(Map<String, dynamic> json) {
    return ResearchNotification(
      id: json['id'] as int? ?? 0,
      title: json['title'] as String? ?? 'Notification',
      body: json['body'] as String? ?? '',
      notificationType: json['notification_type'] as String? ?? 'general',
      referenceId: json['reference_id'] as int?,
      referenceType: json['reference_type'] as String?,
      isRead: json['is_read'] as bool? ?? false,
      createdAt: json['created_at'] as String?,
    );
  }
}
