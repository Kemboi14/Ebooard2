import uuid
from django.db import models
from django.utils import timezone
from apps.accounts.models import User

class Motion(models.Model):
    """Board motion for voting"""
    
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('proposed', 'Proposed'),
        ('debate', 'Under Debate'),
        ('voting', 'Voting Open'),
        ('passed', 'Passed'),
        ('failed', 'Failed'),
        ('withdrawn', 'Withdrawn'),
        ('tabled', 'Tabled'),
    ]
    
    VOTING_TYPE_CHOICES = [
        ('simple_majority', 'Simple Majority'),
        ('qualified_majority', 'Qualified Majority'),
        ('two_thirds', 'Two-Thirds Majority'),
        ('unanimous', 'Unanimous'),
        ('consensus', 'Consensus'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=200)
    description = models.TextField()
    background = models.TextField(blank=True, help_text="Background information for the motion")
    
    # Voting configuration
    voting_type = models.CharField(max_length=20, choices=VOTING_TYPE_CHOICES, default='simple_majority')
    required_votes = models.PositiveIntegerField(help_text="Number of votes required to pass")
    voting_deadline = models.DateTimeField(help_text="Deadline for voting")
    
    # Status and metadata
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    proposed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='proposed_motions')
    seconded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='seconded_motions')
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    voting_started_at = models.DateTimeField(null=True, blank=True)
    voting_ended_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        verbose_name = 'Motion'
        verbose_name_plural = 'Motions'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Motion {self.id}: {self.title}"
    
    @property
    def is_voting_open(self):
        """Check if voting is currently open"""
        return (self.status == 'voting' and 
                timezone.now() <= self.voting_deadline and 
                not self.voting_ended_at)
    
    @property
    def total_votes(self):
        """Get total number of votes cast"""
        return self.votes.count()
    
    @property
    def yes_votes(self):
        """Get number of yes votes"""
        return self.votes.filter(choice='yes').count()
    
    @property
    def no_votes(self):
        """Get number of no votes"""
        return self.votes.filter(choice='no').count()
    
    @property
    def abstain_votes(self):
        """Get number of abstain votes"""
        return self.votes.filter(choice='abstain').count()
    
    @property
    def is_passed(self):
        """Check if motion passed based on voting type"""
        if self.status != 'voting':
            return self.status == 'passed'
        
        total = self.total_votes
        yes_count = self.yes_votes
        
        if self.voting_type == 'simple_majority':
            return yes_count > total / 2
        elif self.voting_type == 'qualified_majority':
            return yes_count > total * 0.6  # 60% qualified
        elif self.voting_type == 'two_thirds':
            return yes_count > total * 2 / 3
        elif self.voting_type == 'unanimous':
            return yes_count == total and self.no_votes == 0
        elif self.voting_type == 'consensus':
            return self.no_votes == 0 and self.abstain_votes <= total * 0.1  # Max 10% abstain
        
        return False
    
    def get_absolute_url(self):
        """Get absolute URL for motion"""
        return f"/voting/motions/{self.id}/"

class VotingSession(models.Model):
    """Voting session to manage voting periods"""
    
    STATUS_CHOICES = [
        ('scheduled', 'Scheduled'),
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    meeting = models.ForeignKey('meetings.Meeting', on_delete=models.SET_NULL, null=True, blank=True, related_name='voting_sessions')
    
    # Session timing
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='scheduled')
    
    # Access control
    eligible_voters = models.ManyToManyField(User, related_name='eligible_sessions', blank=True)
    
    # Metadata
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_sessions')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Voting Session'
        verbose_name_plural = 'Voting Sessions'
        ordering = ['-start_time']
    
    def __str__(self):
        return f"Voting Session: {self.title}"
    
    @property
    def is_active(self):
        """Check if session is currently active"""
        now = timezone.now()
        return (self.status == 'active' and 
                self.start_time <= now <= self.end_time)
    
    @property
    def motions_count(self):
        """Get number of motions in this session"""
        return self.motions.count()

class VoteOption(models.Model):
    """Options for multiple choice votes"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    motion = models.ForeignKey(Motion, on_delete=models.CASCADE, related_name='vote_options')
    text = models.CharField(max_length=200)
    order = models.PositiveIntegerField(default=0)
    
    class Meta:
        verbose_name = 'Vote Option'
        verbose_name_plural = 'Vote Options'
        ordering = ['order']
        unique_together = ['motion', 'order']
    
    def __str__(self):
        return f"{self.motion.title} - Option {self.order}: {self.text}"

class Vote(models.Model):
    """Individual vote cast by a user"""
    
    CHOICE_CHOICES = [
        ('yes', 'Yes'),
        ('no', 'No'),
        ('abstain', 'Abstain'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    motion = models.ForeignKey(Motion, on_delete=models.CASCADE, related_name='votes')
    voter = models.ForeignKey(User, on_delete=models.CASCADE, related_name='votes')
    choice = models.CharField(max_length=10, choices=CHOICE_CHOICES)
    vote_option = models.ForeignKey(VoteOption, on_delete=models.SET_NULL, null=True, blank=True, related_name='votes')
    
    # Vote details
    comment = models.TextField(blank=True, help_text="Optional comment explaining vote")
    is_anonymous = models.BooleanField(default=False, help_text="Vote anonymously (identity hidden from others)")
    
    # Metadata
    cast_at = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    
    class Meta:
        verbose_name = 'Vote'
        verbose_name_plural = 'Votes'
        ordering = ['-cast_at']
        unique_together = ['motion', 'voter']  # One vote per user per motion
    
    def __str__(self):
        voter_name = "Anonymous" if self.is_anonymous else self.voter.get_full_name()
        return f"{voter_name} - {self.get_choice_display()} - {self.motion.title}"

class VoteResult(models.Model):
    """Final results for completed votes"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    motion = models.OneToOneField(Motion, on_delete=models.CASCADE, related_name='result')
    
    # Results
    total_votes = models.PositiveIntegerField(default=0)
    yes_votes = models.PositiveIntegerField(default=0)
    no_votes = models.PositiveIntegerField(default=0)
    abstain_votes = models.PositiveIntegerField(default=0)
    
    # Outcome
    passed = models.BooleanField()
    voting_type = models.CharField(max_length=20, choices=Motion.VOTING_TYPE_CHOICES)
    
    # Details
    summary = models.TextField(blank=True, help_text="Summary of voting results")
    
    # Metadata
    certified_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='certified_results')
    certified_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Vote Result'
        verbose_name_plural = 'Vote Results'
    
    def __str__(self):
        return f"Result for {self.motion.title}: {'Passed' if self.passed else 'Failed'}"
