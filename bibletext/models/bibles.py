from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils.translation import ugettext_lazy as _

import bible # python-bible module. See http://github.com/jasford/python-bible

from fields import VerseField


class BookBase(models.Model):
    """
    BookBase (Book) model - implement this abstract class for book information in different languages.
    """
    name = models.CharField(max_length=50)
    testament = models.CharField(max_length=2, choices=(('OT', _('Old Testament')), ('NT', _('New Testament'))), default='OT')
    abbr = models.CharField(max_length=10)
    altname = models.CharField(max_length=150, blank=True,
        help_text=_('Alternate (long form) name, eg: "The Gospel according to St John"'))
    
    def __unicode__(self):
        return self.name
    
    class Meta:
        app_label = 'bibletext'
        abstract = True


class Book(BookBase):
    " Implements the BookBase abstract model for the English language texts. "
    class Meta:
        db_table = 'bibletext_books'
        app_label = 'bibletext'


class BiblePassageManager(models.Manager):
    " NB: verse and passage work with English at present. "
    
    def verse(self, reference):
        " Takes textual verse information and returns the Verse. "
        if self.model.translation and reference[-3] != self.model.translation:
            reference += ' '+self.model.translation
        verse = bible.Verse(reference)
        return self.get_query_set().get(book__pk=verse.book, chapter=verse.chapter, verse=verse.verse)
    
    def passage(self, start_reference, end_reference=None):
        """
        Takes textual passage information and returns the Verse(s).
        Note: you can't just input 'Romans 1:1-2:3',
        you'll need to do ('Romans 1:1', 'Romans 2:3') for the time being.
        """
        if not end_reference: # Probably just a single verse, return a list anyway.
            end_reference = start_reference
        
        if self.model.translation and start_reference[-3] != self.model.translation:
            start_reference += ' '+self.model.translation
        if self.model.translation and end_reference[-3] != self.model.translation:
            end_reference += ' '+self.model.translation
        
        # NB: len(passage) gives us the number of Verses in the passage.
        passage = bible.Passage(start_reference, end_reference)
        # We'll get the number of verses from the start like so to save a db lookup:
        in_the_beginning = 'Genesis 1:1'
        if self.model.translation:
            in_the_beginning += ' '+self.model.translation
        start_pk = len(bible.Passage(in_the_beginning, start_reference))
        return self.get_query_set().order_by('id').filter(pk__gte = start_pk)[:len(passage)]


class VerseText(models.Model):
    """
    VerseText (Bible) model - implement this abstract class for translations/versions.
    Each record (object) will be a single verse.
    """
    book = models.ForeignKey(Book)
    chapter = models.PositiveIntegerField(default=1)
    verse = models.PositiveIntegerField(default=1)
    text = models.TextField()
    
    translation = None # Use the translation code (KJV, NKJV etc) here according to what python-bible supports.
    books = Book # If you have a foreign language Bible, create a model that implements BookBase and go from there.
    
    objects = BiblePassageManager()
    
    def __unicode__(self):
        return u'%s %d:%d' % (self.book, self.chapter, self.verse)    
    
    class Meta:
        ordering = ('id') # ('book__id', 'chapter', 'verse')
        unique_together = [('book', 'chapter', 'verse')]
        app_label = 'bibletext'
        abstract = True
    
    @classmethod
    def register_version(cls, *versions):
        """
        Register a list of bible versions::

            VerseText.register_version(
                KJV,
                )
        
        You can call this function as often as you like to register more bible versions.
        """
        if not hasattr(cls, 'versions'):
            cls.versions = []
        
        for version in versions:
            version_content_type = ContentType.objects.get_for_model(version)
            if version_content_type.pk not in cls.versions:
                cls.versions.append(version_content_type.pk)
    
    @models.permalink
    def get_absolute_url(self):
        return ('bibletext_verse_detail', (), {
            'version':self.translation,
            'book_id': self.book.pk,
            'chapter': self.chapter,
            'verse': self.verse})
    
    @models.permalink
    def get_chapter_url(self):
        return ('bibletext_chapter_detail', (), {
            'version':self.translation,
            'book_id': self.book.pk,
            'chapter': self.chapter})
    
    #---------------------
    # Next/Previous Verses
    
    @property
    def next_verse(self):
        if hasattr(self, '_next_verse'):
            return self._next_verse
        try:
            self._next_verse = self.__class__.objects.get(pk=self.pk+1)
            return self._next_verse
        except self.__class__.DoesNotExist:
            self._next_verse = None
            return self._next_verse
    
    @property
    def prev_verse(self):
        if hasattr(self, '_prev_verse'):
            return self._prev_verse
        if self.book_id == 1 and self.chapter == 1 and self.verse == 1:
            self._prev_verse = None # Genesis 1:1 has no previous verse.
            return self._prev_verse
        self._prev_verse = self.__class__.objects.get(pk=self.pk-1)
        return self._prev_verse
    
    #---------------------
    # Next/Previous Books
    
    @property
    def next_book_pk(self):
        next_book_pk = self.book_id + 1
        if next_book_pk <= 66:
            return next_book_pk
        return None
    
    @property
    def prev_book_pk(self):
        prev_book_pk = self.book_id - 1
        if prev_book_pk > 0:
            return prev_book_pk
        return None
    
    @property
    def next_book(self):
        if self.next_book_pk:
            return self.books.objects.get(pk=self.next_book_pk)
        return None
    
    @property
    def prev_book(self):
        if self.prev_book_pk:
            return self.books.objects.get(pk=self.prev_book_pk)
        return None


# Implementation of VerseText
class KJV(VerseText):
    " Implements the VerseText abstract model for the Authorized Version (KJV) text. "
    
    translation = 'KJV'
    
    class Meta:
        db_table = 'bibletext_kjv'
        app_label = 'bibletext'
        verbose_name = 'King James (Authorized) Version'

VerseText.register_version(KJV) # Make sure the KJV is available for usage.