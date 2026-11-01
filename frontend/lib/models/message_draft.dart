class MessageDraft {
  final int assignmentId;
  final int messageLogId;
  final String whatsappUrl;
  final String phoneNumber;
  final String waPhone;
  final String messageText;
  final String? disclaimer;
  final String? memberName;
  final String? taskTitle;
  final DateTime? deadline;
  bool isSent;

  MessageDraft({
    required this.assignmentId,
    required this.messageLogId,
    required this.whatsappUrl,
    required this.phoneNumber,
    required this.waPhone,
    required this.messageText,
    this.disclaimer,
    this.memberName,
    this.taskTitle,
    this.deadline,
    this.isSent = false,
  });

  factory MessageDraft.fromJson(Map<String, dynamic> json, {String? memberName, String? taskTitle, DateTime? deadline}) {
    return MessageDraft(
      assignmentId: (json['assignment_id'] as num?)?.toInt() ?? 0,
      messageLogId: (json['message_log_id'] as num?)?.toInt() ?? 0,
      whatsappUrl: json['whatsapp_url'] as String? ?? '',
      phoneNumber: json['phone_number'] as String? ?? '',
      waPhone: json['wa_phone'] as String? ?? '',
      messageText: json['message_text'] as String? ?? '',
      disclaimer: json['disclaimer'] as String?,
      memberName: memberName,
      taskTitle: taskTitle,
      deadline: deadline,
      isSent: false,
    );
  }
}
